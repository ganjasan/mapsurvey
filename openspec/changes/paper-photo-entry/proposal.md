## Why

Epic #350 items 1 and 2 are merged: a filled form can be entered by hand (operator entry, #355) and
every printed page carries a form code that names a `PrintedForm` row (#489). The stack of forms
after an open house is still keyed in by hand, question by question — the consultant with 150 forms
in two languages does not do it, and the student with a phone at the event has nowhere to put the
photos. Item 3 (#495) turns photos or scans of filled forms into prefilled entries that the
operator checks against the picture and saves, so entering a form becomes reading it.

The first build grouped pages by upload order and page number. On a real test it split one filled
form into two responses: photos arrive in any order, from several phones, with pages missed and
re-shot. The order of arrival cannot say whose page it is; only the paper can.

## What Changes

- **Numbered copies.** *Print a paper form* offers **Numbered copies** (1…200 per print) next to
  **One copy to photocopy**. Copy numbers belong to the survey and only grow (`PrintRun`), so every
  printed questionnaire is unique however many times the creator prints. Each page carries the copy
  number in two QR codes (bottom corners, 20 mm, error level H) and in print (`#37` top right,
  `MS-<form> · #37 · Page 2 of 4` in the footer). The form is laid out once per print; every copy's
  page reuses that layout as a PDF form object, so 20 copies cost about one copy in bytes.
- **The code is read locally, never by a model.** zxing-cpp decodes the QR at full resolution in the
  worker (whole page, then enlarged corners). No AI call reads a code.
- **Paper responses, placed by the code.** Every filled form is a *paper response* (`PaperSheet`),
  labelled "Copy 37" or "Response 4". A page of a numbered copy goes to that copy's response
  whatever file, card or order it came in; a page of an unnumbered form goes where the operator put
  it (*New response* + photos, or one PDF per form in *Upload a stack*); a loose photo of an
  unnumbered form is set aside with the reason. A re-shot page replaces the earlier photo, which can
  be restored. A page of a stored response is set aside, never silently added.
- **One page, *Paper responses*,** under *Responses → Enter a response → From photos of paper forms*:
  what was printed and what came back, the open responses as cards with a slot per page,
  *New response*, *Upload a stack* (with the camera on a phone), *Check next*, set-aside photos with
  *Add to response*, and the last stored responses. A hidden inbox (`PaperBatch`, one per survey)
  only numbers things; the operator never manages batches.
- **One vision call per page.** The model (Gemini) receives the page image and the exact items
  printed on it and returns per-field values with a confidence and an *unreadable* flag.
  `LLMProvider.complete_structured` gains image input. Geo questions are not read (item 4); file
  questions are "online only".
- **Check page by page of the printed form.** The photograph on the left, the questions printed on
  that page on the right, prefilled; doubtful and blank fields marked; a stepper over the pages; a
  page that was not photographed is attached right there. Saving the last page stores the session
  (`source='paper'`, the form's version and language, `paper_sheet`); *Check next* goes on.
- **Images live until the response is stored or skipped**, then are deleted; open responses
  untouched for 30 days are skipped by `sweep_paper_batches` (in `reclaim.sh`). Rows stay.
- **Cost goes to PostHog at once**: every call is an `AIGenerationEvent` and a `$ai_generation`
  (trace `paper-response-<id>`). `check_quota(org, 'paper_page')` runs before each call — a seam,
  no number yet.
- **Events**: `paper_response_created`, `paper_page_recognised`, `paper_sheet_entered` — ids and
  counts, never page content. Export carries `paper_copy`.

## Capabilities

### New Capabilities
- `paper-photo-entry`: paper responses, uploads and pages; ingest with the local code read;
  deterministic placement by copy; vision extraction per page; the *Paper responses* page; checking
  page by page; image lifetime and the sweep; the quota kind and the events.

### Modified Capabilities
- `operator-entry`: the header links to *Paper responses*; a paper session skips the header, is
  prefilled and rendered with the page pane; the Saved page offers *Check next*; the drawer and
  exports name the paper copy.
- `printable-form`: two QR codes with the copy number, the footer line and `#copy`; numbered copies
  and `PrintRun`; `PrintedForm.layout` lists the items drawn on every page.
- `ai-survey-generation`: `complete_structured` accepts images; the quota seam takes a kind other
  than survey drafting.

## Impact

- **Models / migrations** (`0113`): `PrintRun`; `PaperBatch` (the inbox), `PaperUpload`, `PaperPage`,
  `PaperSheet` (private media tier, `paper_pages/<uuid>.jpg`); `SurveySession.paper_sheet`.
- **Code**: `survey/print/` (copies canvas, two QR, `form_code` payload `MSFORM:…`), `survey/paper/`
  (ingest, codes, sheets, extract, prompts, review, accounting), `survey/paper_views.py`,
  `survey/tasks.py`, `survey/operator_entry_views.py`, `survey/views._build_section_context`,
  `survey/ai/client.py`, `survey/ai/quota.py`, `survey/share_views.py`, `survey/export.py`.
- **Dependencies**: `pypdfium2`, `pillow-heif`, `zxing-cpp` (bundled wheels, no apt), `pypdf` moves to
  runtime packages.
- **Memory**: the web worker never decodes an image; decoding, splitting and the model call run in
  Celery one page at a time; originals are deleted once split.
- **Help centre**: `how-to/enter-paper-forms-from-photos` in the same PR; the printing page names
  numbered copies.
- **Not in this change**: marks on the printed map → coordinates (item 4); direct-to-S3 presigned
  uploads; any OMR path.
