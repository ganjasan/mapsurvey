## Context

Items 1 and 2 of epic #350 give this change its two ends. Operator entry (`survey/operator_entry_views.py`)
walks a `SurveySession` with `source != online` through the respondent partials, stores through
`views.save_section_answers`, and already prefills a section from the session's `Answer` rows
(`views._build_section_context` builds `initial` from them). The printed form (`survey/print/`) puts a
form code on every page — `MS-<form>-<page>` in the footer and a QR `ms:form:<form>:<page>:<pages>` —
that names a `PrintedForm` row: canonical survey, `version_number`, `language`, `paper`, and a
`layout` dict per page that today records only map frames.

What is missing between them: a place to put many photographs, a worker that turns them into pages
and reads what is on each, and a review that is the entry form with the picture beside it.

Constraints that shape the design (owner, 2026-10-29):
- Files are big and many: phone photos of 3–8 MB, scanner PDFs of 20–50 pages, dozens of files at
  once or a few at a time while the event is still running.
- The operator must be able to check the recognition against the picture and fix it there and
  then — so the picture lives until the sheet is entered, not "until extracted".
- Pages are grouped into sheets by upload order and page number; the review is the entry flow by
  sections, not a new form renderer.
- The web worker keeps the RSS of its largest request (2026-09-15); nothing on the request path may
  decode an image or parse a PDF.

## Goals / Non-Goals

**Goals**
- From photos to a prefilled, reviewed, stored `paper` session with no hand typing beyond
  corrections.
- Every stage visible: upload progress per file, recognition state per sheet, doubtful fields per
  section.
- One extraction call per page, bounded by what the page actually carries.
- Nothing written to `Answer` before the operator saves a section; nothing guessed for a page we
  cannot place.

**Non-Goals**
- Reading marks on the printed map (item 4). The page image and `PrintedForm.layout` are kept for it.
- OMR, scanner drivers, our own handwriting model, batch "accept all without looking".
- Presigned direct-to-S3 uploads (only if the per-file Django upload proves to hold memory).

## Decisions

### D1. Four rows: batch, upload, page, sheet

```
PaperBatch        survey (canonical), organization, created_by, status open|closed,
                  created_at, last_activity_at
PaperUpload       batch, file (private tier, paper_uploads/<uuid>), original_name, size,
                  seq (upload order), status queued|split|failed, error, pages_count
PaperPage         batch, upload, sheet (nullable), seq (global order in the batch),
                  image (private tier, paper_pages/<uuid>.jpg), width, height,
                  printed_form (nullable), page_number (nullable), pages_total (nullable),
                  code_source qr|text|none, status queued|recognised|unrecognised|failed,
                  extraction JSON, error, created_at
PaperSheet        batch, seq, printed_form (nullable), status recognising|review|incomplete|
                  entered|skipped|unrecognised, session (OneToOne SurveySession, nullable),
                  extraction JSON (merged over its pages), doubtful_count, entered_at
SurveySession     + paper_sheet FK (SET_NULL) — the drawer and exports can say "sheet 7 of batch 3"
```

`seq` on uploads and pages is assigned in the upload request from the batch's counter under
`select_for_update`, so "upload order" is the order the server received the files, which is what
the operator sees in the list. A multi-page PDF yields consecutive `seq`s.

**Why a separate `PaperUpload`**: a 50-page PDF is one file with one failure mode ("not a PDF",
"encrypted") and one progress line until it is split; the pages do not exist yet. Deleting the
original after the split keeps storage at one JPEG per page.

### D2. Ingest runs in Celery, one page at a time

`survey/paper/ingest.py`, task `ingest_paper_upload(upload_id)`:
1. Sniff the type from the bytes (JPEG/PNG/WEBP/HEIC/HEIF/PDF); anything else → `failed` with a
   message the list shows ("Not a photo or PDF").
2. PDF → `pypdfium2` renders page by page at 150 dpi; images → Pillow (`pillow-heif` registers
   HEIC), EXIF-transposed. Each page is normalised to a JPEG with the long side ≤ 2200 px,
   quality 85 — what the browser shows, what the decoder reads, what the model receives. ~500 KB
   a page; a 12 MP photo decodes to ~50 MB for the duration of one page and is dropped before the
   next.
3. Each page is saved as a `PaperPage` (`status=queued`), then `recognise_paper_page.delay(id)`.
4. The original upload is deleted from storage; `PaperUpload.status=split`, `pages_count` set.

Both wheels bundle their native library (`pypdfium2` ships pdfium, `zxing-cpp` ships the decoder,
`pillow-heif` ships libheif) — no apt line in the Dockerfile. The image is python:3.12-slim on
Debian trixie; the wheels are manylinux2014 and import cleanly there (checked in the task list).

### D3. The form code is read locally first, by the model second

`survey/paper/codes.py::read_code(image) -> (form_id, page, pages, source)`:
1. `zxing-cpp` over the normalised page, then over a 2× upscale of the four corners (a phone
   photo at 2200 px gives the 16 mm QR ~120 px — plenty; the upscale is for skewed shots).
2. If no QR decodes, one small vision call "read the form code `MS-…` in the footer" through the
   same client (schema `{code}`); `form_code.parse` tolerates 0/O and 1/I. `code_source` records
   which way the code came so PostHog can tell how often the fallback runs.
3. A code whose `PrintedForm` does not belong to this batch's survey, or no code at all →
   `unrecognised`; the page stays in the batch, listed under "Not recognised", with *Assign to
   form…* (pick the printed form and page by hand) and *Remove*.

### D4. Grouping is incremental and by (order, page number)

`survey/paper/sheets.py::place_page(page)` runs when a page gets its code, in `seq` order:
- `page_number == 1`, or no open sheet in the batch → a new `PaperSheet(seq=next)`.
- Otherwise append to the batch's last sheet when it has the same `printed_form` and the page
  number is the sheet's last + 1; else a new sheet, and the sheet it could not continue is marked
  `incomplete` (missing page), as is the new one (starts past page 1).
- A sheet is `review` when it holds pages 1…`pages_total` of one form; `incomplete` otherwise.
  Incomplete sheets still open for review — the operator sees the missing page as "page 2 of 3
  not uploaded" and may enter what there is.

Pages that arrive out of `seq` order (the worker finishes a small photo before a big PDF ahead of
it) are placed when their turn comes: `place_page` processes the batch's unplaced pages in `seq`
order and stops at the first one still `queued`. The operator can drag a page to another sheet or
to "new sheet" in the batch list (`move_page` endpoint); a moved page is `pinned` and never
regrouped by the automatic pass.

### D5. One extraction call per page, bounded by the page's items

`PrintedForm.layout["<page>"]["items"]` is new in this change: `pdf.py` appends a zero-height
`ItemMarker(key)` flowable before each section heading, group heading and question block, whose
`draw()` records `"section:<code>"` / `"group:<code>"` / `"question:<code>"` into `records` under
the page reportlab is drawing. Old forms (printed before this change) have no item map; for them
every page gets the whole structure and the model is told to return only what the page shows.

`survey/paper/extract.py::extract_page(page)`:
- Items come from the form's version header (`PrintedForm.survey` family, `version_number`) in
  `PrintedForm.language`, for the respondent surface — the same walk `pdf.py` prints from
  (`print.pdf.plan_items` is factored out so both use it). Per question: `code`, `type`, `name`,
  `options [{code, label}]` with `other` write-in flag, `bounds` for range/rating, `max` for
  multichoice. Geo, `layer_objects`, `photo/audio/document`, `html`, `image` are not asked.
- Response schema: `{"fields": [{"code", "value": string | string[] | null, "confidence": 0..1,
  "unreadable": bool}]}`; typed per question: choice → option code, multichoice/ranking → codes,
  number/range/rating → the number as text, thumbs → `"1"`/`"0"`, text/text_line/datetime →
  transcription, write-in → `other` text in a companion field `<code>__other`.
- The call is `provider.complete_structured(system, user, schema, images=[(mime, bytes)],
  max_tokens=8000)`; `AIGenerationEvent(kind='paper_page')` records usage and outcome, like a
  draft. `check_quota(organization, 'paper_page')` runs before the call — permissive today, the seam
  for a per-plan allowance tomorrow. A hard cap of 500 pages per batch and 40 MB per file is not
  quota but sanity.
- `DOUBTFUL = 0.75`: a field below it, or `unreadable`, is doubtful. The sheet's `extraction` is
  the merge of its pages' fields by code (a later page never overwrites an earlier page's value
  for the same code — a question is printed once), `doubtful_count` the number of doubtful fields.

**Cost goes to PostHog at once** (owner, 2026-10-29): every call — extraction and the footer-code
fallback — emits `$ai_generation` through `product_events.emit_llm_generation` the moment the
`AIGenerationEvent` row is written, not at the end of the batch: `$ai_span_name` = the event's
kind (`paper_page` / `paper_code`; the helper stops hard-coding `survey_draft`), `$ai_trace_id` =
`paper-batch-<batch id>` so a batch's pages roll up to one trace on the LLM Analytics dashboard,
`$ai_input_tokens` (Gemini counts the image in `promptTokenCount`, so the computed cost includes
it), `$ai_output_tokens` with thinking folded in as for drafts, latency, `$ai_is_error` on a
failure, plus `survey_id`, `batch_id`, `page_number` — ids only. PostHog prices the tokens by
model; nothing in our database stores a dollar figure.

Thinking level: the extraction call sends `AI_THINKING_LEVEL` like a draft. Transient provider
errors retry twice with backoff in the task (the same classification the client already makes);
a final failure leaves the page `failed` with *Retry* in the list.

### D6. Review is the entry flow, prefilled from the sheet

`POST /editor/surveys/<uuid>/responses/paper/<batch>/sheets/<sheet>/enter/`:
- Creates the sheet's `SurveySession` if none: `survey` = the printed form's version header,
  `language` = the form's language, `source='paper'`, `entered_by`, `opened_by_kind` as item 1,
  `paper_sheet=sheet`. The header step of item 1 is skipped — the form code answered its three
  questions. Redirects to the first visible section of the ordinary entry URL.
- `entry_section` sees `session.paper_sheet` and passes `prefill=sheet_prefill(sheet, section)` to
  `_build_section_context`, which uses it as `initial` for questions that have no `Answer` row yet
  (a saved section's rows win, exactly as now). `sheet_prefill` speaks the dialect the existing
  `initial` dict speaks (choice → `str(code)`, multichoice → list, number → value, write-in →
  `other_option.field_name(code)`), so `SurveySectionAnswerForm` is untouched.
- The context also carries `paper_doubtful` (codes) and `paper_blank` (codes the model saw empty),
  rendered into `#section-data` as `data-paper-doubtful`/`data-paper-blank`; `paper_review.js`
  marks the field wrappers (`.paper-doubtful` amber, `.paper-blank` grey) and adds a count to the
  entry bar ("3 fields to check"). Nothing is auto-accepted silently: every section is shown.
- **The page pane**: `entry_section` picks the page whose `items` contain `section:<code>`
  (else the sheet's first page) and renders `editor/operator_entry/_paper_pane.html`: the image
  (served by `paper_page_image`, the gated private-tier stream used for comment attachments),
  zoom (CSS transform, wheel + buttons), rotate 90°, a page switcher over the sheet's pages, and a
  "Map" toggle on `map`-layout sections. On a `form`-layout section the pane takes the stage
  (the empty side of the layout); on a `map` section it overlays the map and the toggle swaps
  them — geo answers still need the map, item 4 will read marks from the same pane.
- Saving the last section → `entry_saved`: `mark_completed()`, `sheet.status='entered'`,
  `entered_at`, `delete_sheet_images.delay(sheet_id)`; the Saved page's *Next sheet* opens the
  batch's next `review`/`incomplete` sheet (POST enter) or returns to the batch list when none.
  `paper_sheet_entered` carries `fields_total`, `fields_doubtful`, `fields_changed` (diff between
  prefill and the stored answers, by code) — the quality signal for the prompt.
- *Skip* on a sheet: `status='skipped'`, images deleted, session (if any, empty) trashed.

### D7. Uploads stream to storage, the list polls

- `POST …/paper/<batch>/upload/` takes ONE file per request (multipart `file`), 40 MB max
  (`PAPER_UPLOAD_MAX_BYTES`), creates `PaperUpload` with the next `seq`, saves the `UploadedFile`
  straight into the `FileField` (Django's temporary-file handler has already streamed anything
  over 2.5 MB to disk; `storage.save` streams it on), enqueues `ingest_paper_upload`, answers
  `{id, seq}`. The page JS (`paper_batch.js`) uploads selected files with 3 in flight, XHR for
  per-file progress, and retries a failed request once; the drop zone stays live — adding files
  to an open batch is the normal case.
- `GET …/paper/<batch>/status/` answers the batch counters and every sheet/upload row's state;
  the list polls every 3 s while anything is `queued`/`recognising`, like the dashboard's import
  jobs, and re-renders the sheet list partial through HTMX.
- The batch page is `/editor/surveys/<uuid>/responses/paper/` (list of this survey's batches,
  *New batch*) and `…/paper/<batch>/` (the batch). Entry point: a second item under *Enter a
  response* on Responses — the button becomes a small dropdown: *Type in a response*, *From
  photos*. Same gate as item 1 (`entry_gate`: editor role, `operator_entry` feature per request).

### D8. Images live until the sheet is done; a cron sweeps the rest

- `delete_sheet_images(sheet_id)` deletes the pages' images (and the sheet's pages keep their
  rows with `image=''`) when a sheet is entered or skipped.
- `sweep_paper_batches` (management command, Render cron daily, the `reclaim_preview_media`
  pattern: dry run by default, `--delete` to act): closes batches with `last_activity_at` older
  than `PAPER_BATCH_TTL_DAYS=30`, deletes their remaining images and originals. Rows stay.
- `/trust/` gets the sentence: photos of paper forms uploaded by a creator's team are kept until
  the sheet is entered or for 30 days, whichever is first; the model provider receives the page
  image for the duration of the call (the same disclosure the AI draft has).

### D9. `complete_structured` takes images

`LLMProvider.complete_structured(..., images=None)` — a list of `(mime_type, bytes)`. The Gemini
implementation puts each as an `inline_data` part before the user text; the Anthropic
implementation as `image` content blocks. Omitted → the payload is byte-for-byte what it is today
(the existing request-shape tests stay green). `survey/ai/client.py` stays the only module that
knows the wire format.

## Risks / Trade-offs

- **Model reads a checkbox wrong with high confidence** → the review shows every section, not just
  doubtful fields; `fields_changed` in `paper_sheet_entered` measures how often, and the help page
  says what the model is good and bad at (ticks vs. crosses, handwriting). Mitigation in the
  prompt: "a box is marked when it has any ink inside; a struck-through mark is not an answer".
- **A page photographed twice** → two pages with the same (form, page) in a row: the second
  starts a new, incomplete sheet. The list shows "page 2 of 3 — duplicate?" next to it; *Remove*
  is one click. Not auto-dropped: two respondents can share one printed copy's page 2 only on the
  same sheet, but the operator decides.
- **Worker memory with big PDFs** → one page rendered at a time, original deleted after the
  split; the Celery worker is a separate service with its own memory. A 300-dpi A3 scan still
  decodes under 100 MB.
- **S3 round trips per page** (save JPEG, read for the model, stream for the pane) → each is one
  object; the pane image is cached by the browser (`Cache-Control: private, max-age=3600`) since
  the URL is per page.
- **Forms printed before this change** → no `items` map: whole structure per page, the pane
  shows page 1 and the operator flips. Acceptable: the feature ships days after printing did.
- **`entry_section` grows a second prefill source** → kept to one keyword argument
  (`prefill`) and one helper (`sheet_prefill`); the `Answer`-based `initial` code is not touched.

## Migration Plan

1. Migration: the four models, `SurveySession.paper_sheet`, `AI_GENERATION_KIND_CHOICES` +
   `paper_page` (choices change only). Additive; no backfill. `PrintedForm.layout` gains keys on
   the next print; old rows are read with the fallback.
2. Requirements: `pypdfium2`, `pillow-heif`, `zxing-cpp` in the Pipfile; rebuild the image.
3. Settings: `PAPER_UPLOAD_MAX_BYTES`, `PAPER_BATCH_MAX_PAGES`, `PAPER_BATCH_TTL_DAYS`.
4. `render.yaml`: cron `mapsurvey-paper-sweep` (daily, `--delete`), previews off.
5. No kill switch (owner rule): the feature is behind the Pro gate and the entry point; a
   rollback is a revert.

## Open Questions

- Allowance number for `paper_page` per workspace per month — the seam is called with a kind;
  the number is a pricing decision (none yet, as for drafts).
- Whether the Anthropic provider needs image support at all now (`AI_PROVIDER` is Gemini in
  production); implemented for interface symmetry, tested only at the payload level.
