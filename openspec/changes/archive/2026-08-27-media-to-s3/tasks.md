## 1. AWS resources (done ahead of the code, verified live 2026-08-26)

- [x] 1.1 Bucket `mapsurvey-media-prod` in `ap-southeast-2`, in the dedicated AWS project
- [x] 1.2 Block Public Access: `BlockPublicPolicy` and `RestrictPublicBuckets` off; both ACL flags left **on** (ACLs are unused, so leaving them blocked removes a class of accidental exposure)
- [x] 1.3 Bucket policy: anonymous `s3:GetObject` on `media/*` and `previews/*/media/*` only. Verified live — creator prefixes 200, `uploads/*` and `previews/*/uploads/*` 403, presigned URL for a private object 200
- [x] 1.4 Versioning enabled (recovery net for the migration) + lifecycle rule aborting incomplete multipart uploads after 7 days; default encryption is SSE-S3
- [x] 1.5 IAM user `mapsurvey-media` with an inline policy scoped to this bucket; verified its key can read/write/list the bucket and is denied `ListAllMyBuckets`, `CreateBucket` and `iam:ListUsers`

## 2. Settings: make the dormant S3 branch actually work

- [x] 2.1 `mapsurvey/settings.py` — replaced `DEFAULT_FILE_STORAGE`/`STATICFILES_STORAGE` with the `STORAGES` dict; static config hoisted out of the branch entirely, since only media ever moves
- [x] 2.2 `AWS_DEFAULT_ACL = None`, and no `default_acl` on the storage classes — the bucket is `BucketOwnerEnforced` and any ACL fails the upload with `AccessControlListNotSupported`
- [x] 2.3 `AWS_S3_REGION_NAME` from env; `AWS_S3_CUSTOM_DOMAIN = f'{bucket}.s3.{region}.amazonaws.com'`
- [x] 2.4 Key prefixes derived per environment via `mapsurvey/media_prefixes.py` — extracted as a pure, Django-free function so the namespace logic is testable without reloading settings
- [x] 2.5 `USE_S3` unset ⇒ today's filesystem behaviour, unchanged, as the kill switch and the local/test path
- [x] 2.6 `.env.example` — documents every media variable, the two tiers, and that `uploads/` must not be made public
- [x] 2.7 **Found by test 4.6**: `AWS_S3_SIGNATURE_VERSION = 's3v4'` + `AWS_S3_ADDRESSING_STYLE = 'virtual'`. Without them boto3 signed private URLs with the deprecated SigV2 scheme against the region-less global endpoint — the same 307-answering host the public tier had to be fixed for, but on the URLs respondents' private files depend on

## 3. Storage backends

- [x] 3.1 `survey/storage_backends.py` — `PublicMediaStorage` has no `default_acl`, reads `location` from settings at call time, keeps `file_overwrite = False`
- [x] 3.2 Added `PrivateMediaStorage`: private prefix, `querystring_auth = True`, `custom_domain = None` (a custom domain makes `url()` skip signing entirely, which would hand out permanent public links). Nothing writes to it yet — the upload question type is a separate change — but the tier exists and is tested so that change cannot land files in the public prefix
- [x] 3.3 Deleted `StaticStorage` — no callers remain; verified by grep across Python, YAML, shell and the Dockerfile
- [x] 3.4 `mapsurvey/urls.py:66` still branches on `USE_S3` and needs no change

## 4. Tests

- [x] 4.1 With `USE_S3` unset: `default_storage` is `FileSystemStorage` and `MEDIA_URL` is local
- [x] 4.2 With S3 settings overridden (no live AWS): Region-qualified host, ACL `None`, legacy setting names absent from the project's settings module
- [x] 4.3 Prefix isolation: namespace mapping, stray slashes, and the preview-vs-production split
- [x] 4.6 Tier separation: private URLs are SigV4-signed, expire, and hit the regional host; public URLs are unsigned; the two prefixes never nest
- [x] 4.4 `staticfiles` storage is WhiteNoise — a regression here would silently move static to S3
- [x] 4.7 Namespace derivation from Render's environment, including the nameless-preview case that must never fall through to production's prefix
- [x] 4.5 Full suite green after the change: 1578 tests, 1 skipped, 0 failures (495s). No regression from swapping `DEFAULT_FILE_STORAGE` for `STORAGES`
- [x] 4.8 End-to-end against the live bucket (not mocks): public object 200 by unsigned URL, private object 200 by signed URL and 403 with the signature stripped

## 5. Blueprint

- [x] 5.1 `render.yaml` — media env vars on web and worker; credentials as `sync: false` secrets, never literals (public repo). **Not** on the acquisition cron: it writes no media, so it gets no bucket credentials
- [x] 5.2 `MEDIA_S3_NAMESPACE` deliberately absent from the Blueprint — Render cannot know a preview service's name in advance, so settings derive `previews/<service>` from `IS_PULL_REQUEST`/`RENDER_SERVICE_NAME`
- [x] 5.3 `disk:` left in place — the rollback path until the copy is verified in production

## 6. Preview media reclamation

- [x] 6.1 `survey/management/commands/reclaim_preview_media.py` — lists `previews/<service>/` prefixes, asks the Render API which services still exist, deletes only the orphans
- [x] 6.2 Dry run is the default; deleting requires `--delete`
- [x] 6.3 Tests (mocked, no AWS and no Render calls): orphan deleted, live preview retained, dry run removes nothing, missing token is a no-op, and an unreadable service listing raises rather than deleting — a partial listing would make live previews look dead
- [x] 6.4 Wired to a new `mapsurvey-preview-media-reclaim` cron (daily 04:30, previews off, pinned to production's namespace); `RENDER_API_KEY` documented in `.env.example` as disabling reclamation when absent rather than failing

## 7. Production cutover (owner-run, after the PR merges — each step needs a go-ahead)

- [x] 7.0 Migration tool built and self-tested against the live bucket (dry-run → copy → re-run skips → verify, all four modes correct, test objects removed). `aws s3 sync` turned out to be impossible: **there is no AWS CLI in the image** — only Python and boto3 — so `survey/management/commands/migrate_media_to_s3.py` is the copy path
- [x] 7.1 Copied 2026-08-27 via SSH (unblocked by the Dockerfile fix in the same PR: `adduser --system` had left the `app` user with nologin and no `~/.ssh`, which is why every SSH session died after auth). Dry-run → copy → verify: 55/55 files, 72,574,283 bytes, sizes match, disk untouched. One-off jobs were proven NOT to mount the disk (job saw an empty dir while the disk metric read 69 MiB), so SSH was the only path
- [x] 7.2 `USE_S3=TRUE` + media vars set on web and worker via Render API, deployed 2026-08-27. Not on the acquisition cron — it writes no media
- [x] 7.3 Verified in production: `settings` resolve to the bucket, an existing cover serves 200 from the bucket host, a fresh editor upload landed in the bucket and rendered on the respondent page from the bucket domain (browser-driven end-to-end), storage round-trip write/read/delete clean, no S3 errors in logs
- [x] 7.4 `disk:` block removed from the Blueprint, and the disk itself deleted explicitly via `DELETE /v1/disks/…` (204) on 2026-08-27. The PR text claimed Blueprint sync would delete it — wrong: Render stops managing resources removed from the YAML but does not delete them. Proof of the payoff: the first diskless deploy was probed every 2s end to end — 25 probes, 0 non-200, no 502/503 in the logs — where the last disk-attached deploy threw a 502 at the instance swap. The S3 copy (verified) plus bucket versioning is the safety net from here on
- [x] 7.5 `deploy-startup` Purpose updated: the window is eliminated, and reintroducing a disk would bring it back

## 8. Follow-ups (not in this change)

- [ ] 8.1 `survey-serialization` spec still says imports extract "to MEDIA_ROOT/…"; under S3 that is inaccurate wording, not changed behaviour — needs a wording pass
- [ ] 8.2 Rotate the media access key on a schedule (create second key → update Render → delete first)
- [ ] 8.3 Revisit CloudFront if image latency for European respondents becomes a complaint; it can front the existing bucket without moving it
