## Context

Respondents answer through `SurveySectionAnswerForm` (dynamic fields per `input_type`), and geo
sub-answers travel as `properties[code] = [values]` arrays inside the GeoJSON string the popup
serializes — the server resolves each key to a sub-question by code and writes a child `Answer`
(`views.py` ~1058). `Answer` has no file field. There is no respondent-facing upload endpoint.

Storage is ready and waiting: `media-to-s3` (archived 2026-08-27) shipped `PrivateMediaStorage` —
private `uploads/` prefix, SigV4 signed URLs, per-environment namespaces, plus a test asserting the
private tier never gains a `custom_domain` (which would disable signing). This change is its first
writer.

Constraints that shape everything below:

- A popup answer exists client-side before the section is submitted, so file bytes cannot ride the
  section POST. Upload must be asynchronous.
- The upload endpoint is reachable by anonymous respondents. It must be abuse-capped.
- The platform runs on a 0.5-CPU Starter instance; uploads must stream to storage, not buffer in
  worker memory longer than necessary, and the platform file-size cap has to respect that.
- Migration numbering: other worktrees are in flight; check `python manage.py showmigrations survey
  | tail` against master right before merge (standing lesson).

## Goals / Non-Goals

**Goals:**

- Photo (camera on mobile), audio (file + in-browser voice recording), document — as section
  questions and as geo sub-questions.
- Respondent files are private: signed URLs only, never public results, never search-indexable.
- Orphaned uploads (never attached to a submitted answer) do not accumulate forever.
- `USE_S3` off ⇒ everything works on the local filesystem; the test suite touches no network.

**Non-Goals:**

- Video. Explicitly excluded from v1 (size, timeout and egress reasons recorded in the proposal).
- Image processing (thumbnails, EXIF stripping, transcoding). Files are stored and served as
  received; EXIF is *documented* as retained — field collection wants GPS EXIF, privacy review may
  later want it stripped, and that fork deserves its own change.
- Offline queueing for field use. The field epic will need it; this change ships the online path.
- Files on public results pages, in any form.

## Decisions

### An `Upload` row per file, referenced by opaque token

A new model `Upload(id/token: uuid4, session FK, question FK, file: FileField(PrivateMediaStorage),
original_name, content_type, size, created_at, attached: bool)`.

The respondent flow: the widget POSTs the file to `/surveys/<uuid>/upload/` the moment it is
picked/recorded; the server validates and stores it, returns `{token}`. The form (section input or
popup property) carries only the token string. On section submit the server resolves tokens →
`Upload` rows, checks they belong to the current `survey_session` and the same question, marks them
attached, and writes the child/section `Answer` with an FK to the Upload.

*Why not bytes in the section POST for section-level questions and tokens only for popups?* One
path instead of two. Also resubmission (answers are deleted and rewritten on re-POST — the
established prepopulation behaviour) must not require re-uploading the file: the token survives in
the re-rendered form, bytes do not.

*Why a separate model rather than `Answer.file` directly?* An Answer does not exist until section
submit, but the file exists from the moment of upload — something has to own it in between. The
`attached` flag makes orphan reclamation a query (`attached=False, created_at < cutoff`) instead of
a filesystem/bucket walk.

`Answer` gains `upload = ForeignKey(Upload, null=True, on_delete=SET_NULL)` — one nullable column,
no data migration.

### Key layout

`uploads/<survey_uuid>/<token>/<sanitized original name>` (under the environment namespace
established by media-to-s3). The token directory guarantees uniqueness without renaming; keeping
the original filename means the responses ZIP and signed-URL downloads carry human names.
The bucket policy already denies anonymous reads for all of `uploads/*` — verified live during
media-to-s3 (403 without signature, 200 with).

### Validation is server-side, per type, with a platform cap

Per `input_type`: `photo` → image/* (allow-list: jpeg, png, webp, heic/heif, gif), `audio` →
audio/* (webm, ogg, mp4/m4a, mpeg, wav), `document` → pdf, doc(x), xls(x), odt/ods, txt, csv.
Content-type is taken from the file, not trusted from the client alone: magic-bytes check for the
image and pdf families; for audio containers the check is best-effort (magic bytes vary), the
allow-list plus size cap bounds the damage. SVG is deliberately NOT an allowed image type — stored
XSS via SVG served from our origin-adjacent bucket is the classic trap.

Platform cap 25 MB/file (audio at ~1 MB/min is the sizing driver); creator can lower per question
but not raise. Per-session abuse cap: 30 files / 150 MB per `SurveySession`, enforced in the
endpoint with a count/sum query — an anonymous endpoint with no cap is a free CDN for someone.

### Mobile capture and voice recording

- `photo`: `<input type="file" accept="image/*" capture="environment">` — mobile browsers open the
  camera; desktop opens a picker. No JS required for the base path.
- `audio`: the file input (`accept="audio/*"`) is always rendered. When `MediaRecorder` is
  available AND `getUserMedia` grants a microphone, the widget also offers Record/Stop with
  elapsed time and replay; the result becomes a Blob uploaded through the same endpoint
  (`audio/webm;codecs=opus`, Safari falls back to `audio/mp4`). Denied permission or missing API
  degrades to the file input silently. Recording UI states: idle → recording (pulsing dot, mm:ss)
  → recorded (player + re-record ⟳ + uses the shared uploading state).
- Required: the section POST never calls `form.is_valid()` — for every existing type,
  required is enforced by the browser's HTML5 validation only (a recorded platform lesson).
  A hidden input gets no HTML5 validation, so the widget's JS blocks form submit itself when a
  required file question has no token, showing its error state. The server stays consistent with
  the platform: an absent token is an unanswered question, not a 500.
- Upload widget states (shared by all three types): empty → uploading (progress %, cancel) →
  uploaded (name, size, thumbnail for photos via signed URL, replace ✕) → error (message, retry).
  The hidden input holds the token only in `uploaded`.

### Popup integration

The popup form renders the same widget; on Apply, the token lands in
`properties[code] = ["<token>"]` exactly like a text sub-answer, so the GeoJSON path in `views.py`
needs one new branch (`file types → resolve token, set sub_answer.upload`). The upload itself
happens while the popup is open — by the time the user hits Apply the token is normally already
there; Apply with an upload still in flight disables the confirm button until it settles.

### Creator side

- Responses table: file answers render as the original filename linking to a **signed URL minted
  at page render** (15-min expiry — the established `AWS_QUERYSTRING_EXPIRE`); photos additionally
  show an inline thumbnail via the same signed URL.
- Responses geo popup (creator analytics map): file sub-answers appear as links the same way.
- `download_data` ZIP: a `files/<session_id>/<question_code>__<original name>` entry per attached
  upload, read through the storage API (works for both filesystem and S3). The CSV/GeoJSON cell
  carries that relative path, so rows point at the file next to them.
- Public results: nothing. `PublicResultsService` never reads uploads; the spec makes it a stated
  requirement rather than an omission.

### Orphan reclamation

`reclaim_orphan_uploads` management command: deletes `Upload` rows (and their objects) with
`attached=False` older than 48h — long enough to span an abandoned-and-resumed session, short
enough that abuse does not sit for a month. Runs on the existing daily reclaim cron service
alongside preview-media reclamation (same schedule, same service, no new infrastructure). Deleting
a survey already cascades sessions → answers; `Upload.session` FK CASCADE removes rows, and a
post-delete signal removes the stored object.

### Kill switch

`FILE_UPLOAD_QUESTIONS` env var, default ON (the established pattern). Off: the picker group is
hidden, the upload endpoint answers 404, existing file questions render nothing for respondents
(the section still works — fail open, matching conditional-visibility's posture), stored files
remain readable to creators. The rollback story is the env var, not a revert.

## Risks / Trade-offs

- **Anonymous upload endpoint** → session-bound (must present a valid `survey_session` for a
  survey that actually contains a file question), per-session count/byte caps, type allow-lists,
  magic-byte checks, platform size cap. Rate limiting rides the same django-ratelimit machinery as
  registration (fail-open on Redis outage, consistent with the existing posture).
- **HEIC photos from iPhones** → accepted and stored; creators on Windows may not preview them.
  Documented; transcoding is out of scope (see Non-Goals).
- **MediaRecorder browser variance** → progressive enhancement; the file input is always the
  floor. Real-device testing listed in tasks (iOS Safari, Android Chrome at minimum).
- **Signed URLs in the responses table expire mid-session** → 15 min is enough for a viewing
  session; a refresh re-mints. Accepted; alternative (longer expiry) widens the leak window.
- **Uploads during a section the respondent abandons** → exactly what orphan reclamation is for.
- **S3 costs grow with adoption** → caps bound the per-session worst case; watch the bucket size
  metric after launch.

## Migration Plan

1. Ship behind `FILE_UPLOAD_QUESTIONS` default ON; deploy is a no-op for existing surveys (new
   types simply appear in the picker).
2. Migration adds two tables/columns, no backfill. Check migration numbering against master
   immediately before merge (parallel-worktree lesson).
3. The reclaim cron gains the second command; no new Render service.
4. Rollback: env var off. Nothing to restore — existing data is untouched by the feature's absence.

## Open Questions

- None blocking. EXIF retention and video support are recorded as deliberate exclusions with their
  own future changes.
