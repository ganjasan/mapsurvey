## Why

The web service mounts a Render disk at `/home/app/web/mediafiles` to hold uploaded images. A Render
disk attaches to one instance at a time, so Render must stop the old instance before starting the new
one: zero-downtime deploys are unavailable and the service cannot scale past a single instance. The
`deploy-startup` spec already names this as the one remaining blocker — the deploy window "cannot
currently be eliminated … until media moves off the disk". Moving media to S3 removes the disk and
with it both constraints.

The code has carried dormant S3 support since before the Render migration (`USE_S3`,
`survey/storage_backends.py`, `django-storages`), but it has never been switched on in production, and
what is there does not work against a bucket created today.

## What Changes

- Create an S3 bucket for uploaded media in `ap-southeast-2`, in the dedicated AWS project (`aws sts get-caller-identity --profile aws-agent` prints the account).
- Serve `MEDIA_URL` from that bucket; keep static files exactly as they are (WhiteNoise +
  `CompressedManifestStaticFilesStorage` behind Cloudflare). Only media moves.
- Provide **two storage tiers**, because respondent file uploads are the reason this bucket exists:
  creator artwork stays publicly readable, respondent submissions are private and served through
  time-limited signed URLs. This change ships both backends and the key layout; the respondent-facing
  upload question type is a separate change that lands on top.
- Repair the dormant S3 configuration in `mapsurvey/settings.py`, which cannot work as written:
  - `AWS_DEFAULT_ACL = 'public-read'` fails on any bucket created after April 2023 — S3 disables ACLs
    by default (Object Ownership = bucket owner enforced) and rejects the upload with
    `AccessControlListNotSupported`. Public read has to come from a bucket policy instead.
  - `AWS_S3_CUSTOM_DOMAIN = f'{bucket}.s3.amazonaws.com'` is the legacy global endpoint. A bucket in
    `ap-southeast-2` is addressed as `{bucket}.s3.ap-southeast-2.amazonaws.com`; the legacy form
    answers with a redirect that boto3 does not follow for every verb.
  - `DEFAULT_FILE_STORAGE` / `STATICFILES_STORAGE` are the pre-4.2 settings names, superseded by the
    `STORAGES` dict.
- Separate PR-preview media from production media, so a preview environment cannot overwrite or delete
  a real respondent's upload.
- Copy the existing contents of the production disk into the bucket, verify, then remove the `disk:`
  block from `render.yaml`. **BREAKING** for rollback: once the disk is detached, reverting to
  disk-backed media means restoring from the bucket, not flipping an env var.
- Keep `USE_S3` as the kill switch: unset reproduces today's local/dev behaviour on the filesystem.

## Capabilities

### New Capabilities
- `media-storage`: where uploaded media lives, how it is addressed, how environments are isolated from
  each other, and what happens when the object store is unreachable.

### Modified Capabilities
- `render-deployment`: the web service no longer declares a `disk:`; new S3 environment variables
  (`USE_S3`, `AWS_STORAGE_BUCKET_NAME`, `AWS_S3_REGION_NAME`, credentials) join the Blueprint, with
  previews scoped to their own media prefix.
- `deploy-startup`: the stated reason zero-downtime deploys are unavailable no longer holds; the
  requirement text that pins the service to one instance is retired.

## Impact

- `mapsurvey/settings.py` — the `USE_S3` branch, rewritten against current Django and current S3.
- `survey/storage_backends.py` — `PublicMediaStorage` loses `default_acl`; `StaticStorage` becomes
  dead code once static stays on WhiteNoise and should go.
- `render.yaml` — `disk:` removed from the web service; media env vars added to web, worker and cron
  (the worker writes media during AI generation and ZIP import).
- `mapsurvey/urls.py:66` — already branches on `USE_S3` and stops serving `/mediafiles/` locally; needs
  verifying rather than changing.
- `survey/serialization.py` — writes through `FieldFile.save()`, so it follows the storage backend
  unchanged. The `survey-serialization` spec's wording ("extract to MEDIA_ROOT/…") becomes inaccurate
  under S3 and needs a follow-up wording pass, not a behaviour change.
- Data: every existing file under the production disk must be copied before the disk is detached. The
  files are the four creator-authored `ImageField`s (`SurveyHeader.cover_image`, `Question.image`,
  `Story.cover_image`, `PublicResultsBlock.image`) — respondents upload nothing, see design.md. The
  database stores relative paths, which stay valid as S3 keys under the same prefix. The owner
  confirmed the volume is minimal.
- Cost: S3 storage plus egress on every image view, replacing a flat 1 GB disk. Small at current
  volume, but it becomes a per-view cost where it used to be fixed.

### Accepted risk: bucket Region

The bucket goes in `ap-southeast-2` (Sydney) because the AWS project is pinned there — the new AWS
experience forbids creating Regional resources outside the project's Region. Production runs on Render
in Oregon, so every upload crosses the Pacific and every image is served from Australia with no CDN in
front. The owner chose this over enabling advanced capabilities to place the bucket in `eu-central-1`,
with the latency and EU-data-residency trade-off stated (2026-08-26).

Today's files are creator artwork only, but the point of moving to object storage is to let respondents
attach photos, audio and other files to their answers (owner, 2026-08-26). Once that ships, the bucket
holds personal data — photographs taken by members of the public, recordings of their voices — in
Australia. Treat the residency trade-off at full weight, and revisit it before any German or EU
public-sector deal that puts data location in a contract.
