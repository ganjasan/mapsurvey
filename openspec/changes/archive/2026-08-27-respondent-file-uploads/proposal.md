## Why

Respondents can only answer in text, numbers, choices and geometry. The moment a survey needs
evidence — a photo of the broken bench, a recording of street noise, a scanned petition — the
respondent has nowhere to put it. This was the stated reason the S3 bucket exists at all
(owner, 2026-08-26): the private storage tier, signed-URL serving and environment-prefix isolation
shipped in `2026-08-27-media-to-s3` specifically so that this change could land on top without
touching storage again. The field-data-collection epic makes it urgent: "photograph what you
mapped" is the core loop of every field-collection tool we compete with.

## What Changes

- A new **Files** group in the question-type picker with three respondent-answerable types:
  - **`photo`** — image files; on mobile the input offers the camera directly
    (`accept="image/*" capture="environment"`), on desktop a file picker.
  - **`audio`** — audio files, plus **in-browser voice recording** (MediaRecorder): a record
    button with elapsed time, stop, replay, re-record. Recording is progressive enhancement —
    where MediaRecorder or microphone permission is unavailable, the file input still works.
  - **`document`** — PDF and office documents.
  - No video in v1: hundreds of MB per file, upload timeouts on a 0.5-CPU instance, and an
    egress bill we have not modelled. Explicitly out.
- File questions work **both** as section questions and as sub-questions of geo questions —
  a photo attached to the mapped point, in the popup, which is the field-collection scenario.
- Because a popup answer exists before the section is submitted, files upload **asynchronously**:
  a new respondent endpoint stores the file into the private S3 tier immediately and returns an
  opaque reference; the section POST carries references, never bytes. Orphans (uploaded but never
  attached to a submitted answer) are reclaimed server-side.
- Respondent files land in the **private tier** (`uploads/`, signed URLs) — never in the public
  prefix, never on public results pages, never in sitemaps. Creators see them in the Responses
  table and geo popups via expiring signed links, and receive them in the responses-download ZIP.
- `Answer` gets a file reference; **BREAKING** for none — new nullable column, no existing rows
  change. Migration number must be checked against other in-flight worktrees before merge.
- Per-question creator controls: max file size (bounded by a platform cap), required/optional.
  Per-session abuse cap (count + total bytes) server-side, because the endpoint is anonymous.
- Kill switch: `FILE_UPLOAD_QUESTIONS` env var, default ON, following the established pattern —
  off hides the picker group and disables the upload endpoint; stored questions render as
  nothing for respondents (fail open for the rest of the section).
- Local/dev keeps working without AWS: with `USE_S3` unset the same flow stores under
  `MEDIA_ROOT` — same code path, filesystem storage, as established by media-to-s3.

## Capabilities

### New Capabilities
- `file-upload-questions`: the three question types, their respondent UI (including camera
  capture and voice recording), the async upload endpoint, validation, limits, orphan
  reclamation, creator-side viewing and the responses-ZIP export of files.

`media-storage` is deliberately NOT modified: its "Respondent submissions are private"
requirement already states exactly what this change must obey — this is the first writer arriving
to an interface that was specified in advance.

### Modified Capabilities
- `question-type-picker`: a new Files group appears between Map Questions and Display Blocks,
  gated by the kill switch.
- `responses-geo-subanswers`: a file sub-answer of a geo question appears in the creator's
  responses geo popup as a signed link/thumbnail.

## Impact

- `survey/models.py` — `Answer.file` (FileField on the private storage), `INPUT_TYPE_CHOICES`
  +3; one migration.
- `survey/forms.py` — three new field builders in `SurveySectionAnswerForm`.
- `survey/views.py` — upload endpoint (respondent-facing, session-bound, rate-capped);
  section POST resolves references to uploads.
- Popup/section JS — upload widget (progress, retry, replace), MediaRecorder UI for `audio`,
  reference plumbing through the existing sub-answer flow.
- `survey/editor_views.py` + editor templates — picker group, per-question settings.
- `download_data` — files join the responses ZIP under per-session folders.
- `reclaim` — a management command extension or sibling for orphaned uploads.
- Costs: S3 PUT/storage/egress grows with adoption; audio recordings are the big files
  (~1 MB/min). Caps keep the worst case bounded.
