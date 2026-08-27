## Context

Uploaded media currently lives on a Render disk mounted at `/home/app/web/mediafiles`. A Render disk
attaches to exactly one instance, so deploys stop the old container before starting the new one and the
web service cannot scale horizontally. `openspec/specs/deploy-startup/spec.md` already records this as
the last remaining cause of deploy downtime.

The repository has carried unused S3 support since before the Render migration, but it was written
against S3 as it behaved in 2020 and does not work against a bucket created today. The bucket, IAM
principal and policies described below were created and verified against the live account on
2026-08-26 before this document was written — every claim about what S3 accepts here was tested, not
assumed.

Constraints:

- The AWS project is pinned to `ap-southeast-2` by the new AWS experience; Regional
  resources cannot be created elsewhere without activating advanced capabilities. Production runs on
  Render in Oregon. The owner accepted the resulting cross-Pacific hop and the loss of EU data
  residency (see the proposal's "Accepted risk" section).
- Render cannot refresh temporary AWS credentials — there is no OIDC hand-off for its services — so
  the application needs long-lived keys.
- Account plan is FREE with $100 of credits.

## Goals / Non-Goals

**Goals:**

- Uploaded media survives instance replacement, so the web service can drop its disk.
- Production media and PR-preview media cannot touch each other.
- Local development and the test suite keep working with no AWS account and no network.
- The switch is reversible by environment variable until the disk is actually detached.

**Non-Goals:**

- Moving static files. They stay on WhiteNoise with `CompressedManifestStaticFilesStorage` behind
  Cloudflare; that path is faster and cheaper than S3 and hashed filenames already give far-future
  caching.
- A CDN in front of the bucket. Explicitly declined by the owner for this change.
- Private/signed media URLs. Media is public today (served openly from `/mediafiles/`), and this change
  preserves that model rather than changing the product's privacy posture.
- Migrating the database, session storage, or ZIP exports.

## Decisions

### One bucket, prefix per environment

`mapsurvey-media-prod` holds production media under `media/` and PR-preview media under
`previews/<service-name>/`. The prefix comes from a single environment variable, so a preview
environment physically cannot write to production keys.

*Alternative considered — a bucket per environment.* Rejected: Render previews are created and
destroyed per PR, and a bucket cannot be created by the application's own credentials (deliberately —
see the IAM policy below). Prefixes need no provisioning step.

### Public read from a bucket policy, not object ACLs

The bucket has `ObjectOwnership = BucketOwnerEnforced`, which is the default for buckets created today
and means object ACLs are disabled outright. The existing `AWS_DEFAULT_ACL = 'public-read'` would fail
every upload with `AccessControlListNotSupported`. Anonymous read comes from a bucket policy scoped to
`media/*` and `previews/*` instead, and `AWS_DEFAULT_ACL` must be `None`.

Verified live: an object under `media/` returns 200 to an unauthenticated request; an object outside
those prefixes returns 403.

Block Public Access starts fully enabled on a new bucket. `BlockPublicPolicy` and
`RestrictPublicBuckets` were turned off so the policy above can take effect; `BlockPublicAcls` and
`IgnorePublicAcls` stay **on**, because ACLs are not used and leaving those enabled removes a whole
class of accidental exposure. The account's managed SCP/RCP permitted this.

### Regional endpoint, not the legacy global one

`AWS_S3_CUSTOM_DOMAIN` must be `{bucket}.s3.ap-southeast-2.amazonaws.com`. The current
`{bucket}.s3.amazonaws.com` answers **307 Temporary Redirect** for this bucket (verified) — browsers
follow it, boto3 does not for every verb, and it costs every viewer an extra round trip to Virginia
before they reach Sydney.

### A dedicated IAM user with a bucket-scoped inline policy

The IAM user `mapsurvey-media` holds `GetObject`/`PutObject`/`DeleteObject` on
`mapsurvey-media-prod/*` plus `ListBucket`/`GetBucketLocation` on the bucket itself. Nothing else.

Object permissions cover the whole bucket rather than just `media/*` so preview prefixes work without a
policy change per environment; the bucket is dedicated to media, so this is still a tight boundary.

Verified live under the user's own key: writing and listing inside the bucket succeed, while
`ListAllMyBuckets`, `CreateBucket` and `iam:ListUsers` are all denied. A leaked key therefore exposes
media that is already publicly readable, and nothing else in the account.

*Alternative considered — an instance role.* Not available: Render has no AWS identity to assume.

### `STORAGES`, not `DEFAULT_FILE_STORAGE`

Django is 4.2.27, where `DEFAULT_FILE_STORAGE` and `STATICFILES_STORAGE` are deprecated and removed in
5.1; django-storages is 1.14.6, which reads backend options from the `STORAGES` dict. The `USE_S3`
branch defines both entries of `STORAGES` — `default` pointing at the S3 backend, `staticfiles`
staying on WhiteNoise in both branches, since static never moves.

### Versioning on, incomplete uploads expired

Versioning is enabled so a mis-scoped `aws s3 sync` or an accidental delete during migration is
recoverable — respondent uploads have no other copy once the disk is gone. A lifecycle rule aborts
incomplete multipart uploads after 7 days. Default encryption is SSE-S3 (AES256), which S3 applies
automatically.

## Risks / Trade-offs

- **Media served from Sydney to European respondents, no CDN** → Accepted by the owner. Mitigation if
  it bites: put CloudFront in front (allowed from `us-east-1` even under the new experience) without
  moving the bucket.
- **Long-lived access keys in Render's environment** → Scoped to one bucket, verified powerless
  elsewhere. Rotate by creating a second key, updating Render, then deleting the first.
- **Every upload now crosses the Pacific** → Uploads are rare and already asynchronous from the
  respondent's perspective; reads dominate. Watch p95 on image-upload requests after rollout.
- **Egress becomes a per-view cost where a 1 GB disk was flat** → Small at current volume; revisit if
  image-heavy surveys grow.
- **Losing the disk removes the only copy of legacy media** → The disk is detached only after the copy
  is verified object-for-object, and versioning is on before the copy starts.
- **PR previews share a bucket with production** → Prefix isolation plus the fact that previews get
  their own database, so they never hold keys pointing at production objects.

## Migration Plan

1. Bucket, IAM user, policies, versioning, lifecycle — **done** (2026-08-26).
2. Land the code change with `USE_S3` unset everywhere. Nothing changes in production.
3. Copy the disk into the bucket from a Render shell on the web service, using
   `python manage.py migrate_media_to_s3`. **Not** `aws s3 sync`: the image ships Python and boto3
   (via django-storages) but no AWS CLI, so the CLI form in an earlier draft of this plan would simply
   not run there. The command reads its bucket configuration from the environment rather than from
   settings, because it runs while `USE_S3` is still off and those settings do not exist yet. It never
   overwrites an object whose size differs — it reports it — and never touches the disk, so it is
   re-runnable. `--dry-run` previews, `--verify` compares afterwards.
4. Set `USE_S3=TRUE` and the media variables on the web service, worker and cron, and deploy. The disk
   stays mounted — it is now an untouched backup.
5. Verify in production: an existing survey image loads from the bucket domain, a fresh upload lands in
   the bucket, and a ZIP export still contains images.
6. Only then remove the `disk:` block from `render.yaml`. This is the irreversible step and it is what
   restores zero-downtime deploys.

**Rollback:** before step 6, unset `USE_S3` and redeploy — the disk still holds every file. After step
6, rollback means re-adding the disk and syncing back down from the bucket.

## What is on the disk today, and what this storage is for

Today the disk holds only creator-authored artwork. The `image` question type is display-only —
`ShowImageField` / `ShowImageWidget` render an image the creator supplied; there is no file input, and
`serialization.collect_upload_images()` says so outright ("Answer model has no ImageField"). The four
`ImageField`s in the schema are all creator-authored:

| Field | `upload_to` |
|---|---|
| `SurveyHeader.cover_image` | `covers/` |
| `Question.image` | `images/` |
| `Story.cover_image` | `stories/` |
| `PublicResultsBlock.image` | `public_results_blocks/` |

The owner confirmed that volume is minimal (2026-08-26), so the migration itself is a short copy.

**But the reason for object storage is what comes next**: respondents are to be able to attach photos,
audio and other files to their answers (owner, 2026-08-26). That capability is a separate change; this
one lays the storage it will land on. Two consequences follow, and they shape every decision below:

- The bucket will hold personal data — photographs taken by members of the public, recordings of their
  voices — not just survey artwork. The Region trade-off in the proposal is therefore the full-weight
  one, not the reduced one an artwork-only bucket would carry.
- Respondent files must not be readable by URL alone. See the next decision.

### Two storage tiers: public artwork, private submissions

Creator artwork stays anonymously readable — it is already public on every survey page, and public
objects cache well. Respondent submissions are private and reached through time-limited signed URLs.

The split is by key prefix, which is what the bucket policy can express:

| Prefix | Contents | Anonymous read |
|---|---|---|
| `media/` | creator artwork, production | yes |
| `uploads/` | respondent submissions, production | **no** |
| `previews/<service>/media/` | creator artwork, preview | yes |
| `previews/<service>/uploads/` | respondent submissions, preview | **no** |

Verified live against the bucket: the two `media` paths return 200 to an unauthenticated request, both
`uploads` paths return 403, and a presigned URL for an `uploads` object returns 200.

*Alternative considered — everything public, as media is today.* Rejected once respondent uploads
entered scope. A URL is not an access control: links leak into logs, `Referer` headers, exported
archives and screenshots. A photograph of someone's street, or a voice recording, retrievable by
anyone who ever saw the link, is a materially different exposure from a survey cover image.

*Alternative considered — everything private.* Rejected: it would put a signature on every survey
cover and results-page image, breaking edge caching for content that is public by design and
complicating the public results pages for no privacy gain.

## Resolved Questions

- **Disk volume** — minimal, per the owner. Step 3 of the migration is a short copy, and the 1 GB disk
  was never close to full.
- **Preview cleanup** — preview media SHALL be removed once the preview is gone, not on a fixed timer.
  A lifecycle rule expiring `previews/*` after N days is the wrong shape: it would delete media from a
  long-lived PR that is still open. Instead a scheduled reconcile deletes every `previews/<service>/`
  prefix whose Render service no longer exists, which converges within one cron period of the PR
  closing. This needs a Render API token on the cron service.
- **`StaticStorage`** — deleted. Static never moves to S3 in this change, so the class has no caller,
  and leaving a `default_acl = 'public-read'` backend in the tree invites someone to wire it into a
  bucket where ACLs are disabled and get the failure this change exists to remove.
