## Why

Epic #350 items 1 and 2 are merged: a sheet can be entered by hand (operator entry, #355) and every
printed page carries a form code that names a `PrintedForm` row (#489). The stack of sheets after an
open house is still keyed in by hand, question by question — the consultant with 150 sheets in two
languages does not do it, and the student with a phone at the event has nowhere to put the photos.
Item 3 (#495) turns photos or scans of filled sheets into prefilled entries that the operator checks
against the picture and saves, so entering a sheet becomes reading it.

## What Changes

- **A batch of uploads, not a request.** *Responses → Enter a response → From photos* opens a
  `PaperBatch`. The operator drops any number of files — phone photos (JPG/HEIC/PNG), scans, or a
  multi-page PDF — each uploaded as its own request straight to the private media tier with per-file
  progress. A batch stays open: files can be added while earlier ones are already recognised.
- **Pages and sheets.** A Celery task turns each upload into `PaperPage` rows (a PDF is split in the
  worker, HEIC is converted; every page is normalised to a JPEG the browser can show), reads the
  form code from the page's QR, and groups pages into `PaperSheet`s by upload order and page number:
  page 1 starts a new sheet, 2…M continue it; a gap or a repeated page marks the sheet *incomplete*.
  Pages without a readable code, or with a code of another survey, stay in the batch as
  *not recognised*; nothing is guessed.
- **One vision call per page.** The model (Gemini, already in the stack) receives the page image and
  the exact items printed on it — codes, types, option codes, in the form's language — and returns
  per-field values with a confidence and an *unreadable* flag. `LLMProvider.complete_structured`
  gains image input. Geo questions are not read (item 4 of the epic); file questions are "online only".
- **Review is the entry form.** A sheet opens the operator entry flow from item 1 prefilled: the
  photo of the page that holds the section beside the fields (zoom, rotate, page switch), doubtful
  and blank fields highlighted. The operator corrects and saves; the last section stores the session
  through the same writer (`source='paper'`, `entered_by`, linked to the sheet). Nothing reaches
  `SurveySession`/`Answer` before the operator saves the first section.
- **The batch list** shows every sheet with its state — recognising / review (N doubtful) / entered /
  skipped / incomplete / not recognised — the batch's counts, reordering of pages across sheets, and
  *Skip*.
- **Images live until the sheet is entered or skipped**, then are deleted; batches untouched for
  30 days are swept by the same cron pattern as `reclaim_preview_media`. Sheet and batch rows stay
  (which sheet of which batch a session came from) without pictures. This supersedes the epic's
  "deleted after extraction": the operator checks against the screen, not the paper.
- **`PrintedForm.layout` records the items on every page** (`"items": ["section:<code>",
  "question:<code>", …]`) so a page's extraction prompt and the review's page↔section pairing need
  no re-render. Forms printed before this change have no item map and fall back to the whole
  structure per page.
- **Pro feature `operator_entry`**, editor role, per-request — the same gate as item 1 — plus a
  per-workspace allowance of vision pages read by `survey/ai/quota.py` (kind `paper_page`).
- **Events**: `paper_batch_created`, `paper_page_recognised` (outcome, confidence band),
  `paper_sheet_entered` (fields corrected / total) — ids and counts, never page content.

## Capabilities

### New Capabilities
- `paper-photo-entry`: batches, pages and sheets; ingest (split, convert, normalise, read the code,
  group); vision extraction per page with confidence; the batch list; review through the prefilled
  entry form; image lifetime and the sweep; the quota kind and the events.

### Modified Capabilities
- `operator-entry`: the entry header offers *From photos*; an entry section can be prefilled from a
  sheet and rendered with the page image beside it; saving the last section marks the sheet entered
  and links the session to it; *Next sheet* from a sheet opens the next sheet of the batch to review.
- `printable-form`: the `PrintedForm.layout` entry of every page lists the items drawn on it.
- `ai-survey-generation`: `complete_structured` accepts images (the provider-agnostic client
  requirement); the quota seam takes a kind other than survey drafting.

## Impact

- **Models / migrations**: `PaperBatch`, `PaperSheet`, `PaperPage` (private media tier,
  `paper_pages/<uuid>.jpg`), `SurveySession.paper_sheet` (nullable FK), `PrintedForm.layout` shape.
- **Code**: `survey/paper/` (ingest, codes, extraction prompt + schema, grouping, review prefill),
  `survey/paper_views.py` (batch page, upload endpoint, status JSON, sheet actions), `survey/tasks.py`
  (ingest + recognise tasks), `survey/operator_entry_views.py` (prefill, page pane, sheet link),
  `survey/views._build_section_context` (initial values from a source other than `Answer`),
  `survey/print/pdf.py` (item markers per page), `survey/ai/client.py` (image parts),
  `survey/ai/quota.py`, `survey/product_events.py`, the Responses header, a management command
  `sweep_paper_batches` and its Render cron.
- **Dependencies**: `pypdfium2` (PDF → image, bundled wheel), `pillow-heif` (HEIC), `zxing-cpp`
  (QR decode, bundled wheel) — no apt packages; a QR the decoder cannot read falls back to the model
  reading the footer text.
- **Memory**: the web worker never decodes an image — uploads stream to storage; decoding, splitting
  and the model call run in Celery, one page at a time, originals deleted once split.
- **Help centre**: a how-to page `how-to/enter-paper-forms-from-photos` in the same PR; `help_links`
  key `paper_photos`.
- **Trust page**: the sentence on uploaded sheet images (kept until entered, 30-day sweep).
- **Not in this change**: marks on the printed map → coordinates (item 4); direct-to-S3 presigned
  uploads; any OMR path.
