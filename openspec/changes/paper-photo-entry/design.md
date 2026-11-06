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
  then — so the picture lives until the response is stored, not "until extracted".
- (2026-10-31, after the first live check split one form into two responses) The paper decides,
  never the order of arrival: a print mode where every questionnaire is unique, so a shuffled stack
  of scans sorts itself; the page number read without AI; and "one form" starts with an empty
  response the operator then photographs into.
- The web worker keeps the RSS of its largest request (2026-09-15); nothing on the request path may
  decode an image or parse a PDF.

## Goals / Non-Goals

**Goals**
- From photos to a prefilled, reviewed, stored `paper` session with no hand typing beyond
  corrections.
- Every stage visible: upload progress per file, recognition state per page of each response, doubtful fields per
  section.
- One extraction call per page, bounded by what the page actually carries.
- Nothing written to `Answer` before the operator saves a section; nothing guessed for a page we
  cannot place.

**Non-Goals**
- Reading marks on the printed map (item 4). The page image and `PrintedForm.layout` are kept for it.
- OMR, scanner drivers, our own handwriting model, batch "accept all without looking".
- Presigned direct-to-S3 uploads (only if the per-file Django upload proves to hold memory).

## Decisions

### D1. Paper responses, one hidden inbox, numbered copies

```
PrintRun          survey (canonical), form, first_copy, last_copy, created_by, created_at
PaperBatch        survey (canonical), organization, created_by, status, next_upload_seq,
                  next_page_seq, next_sheet_seq, last_activity_at      -- the inbox, one per survey
PaperUpload       batch, seq, sheet (nullable: dropped into a response), expected_page,
                  file (private, paper_uploads/<uuid>), original_name, size, is_pdf,
                  status queued|split|failed, pages_count, error
PaperPage         batch, upload, sheet (nullable), seq, image (private, paper_pages/<uuid>.jpg),
                  printed_form, copy, page_number, pages_total, code_source ''|qr|manual,
                  status queued|recognised|unrecognised|failed|replaced, extraction, error
PaperSheet        batch, seq, printed_form, copy (unique per inbox), source_upload (one PDF of an
                  unnumbered form), status recognising|review|incomplete|entered|skipped,
                  extraction, doubtful_count, created_by, last_activity_at, entered_at
SurveySession     + paper_sheet OneToOne (SET_NULL)
```

Vocabulary (owner, 2026-10-31): the operator works with **paper responses**, labelled "Copy 37"
(the number printed on the paper) or "Response 4" (the inbox number). The model keeps the name
`PaperSheet`; no surface says "sheet" or "batch". `PaperBatch` survived as the per-survey inbox
(`paper.inbox_for`): it holds the counters handed out under `select_for_update` and nothing the
operator sees.

`PrintRun` numbers copies per CANONICAL survey and only grows, across forms, versions, languages
and papers, under `select_for_update` on the canonical `SurveyHeader` row. A copy number therefore
names one printed questionnaire for the life of the survey; a reprint never collides with a stack
already in the field. 200 copies per print bound the PDF and the request time.

**Why a separate `PaperUpload`**: a 50-page PDF is one file with one failure mode ("not a PDF",
"encrypted") and one progress line until it is split; the pages do not exist yet. Deleting the
original after the split keeps storage at one JPEG per page. It also carries where the operator
dropped the file (`sheet`, `expected_page`) and whether it was a PDF (one PDF = one response).

### D2. Ingest runs in Celery, one page at a time

`survey/paper/ingest.py`, task `ingest_paper_upload(upload_id)`:
1. Sniff the type from the bytes (JPEG/PNG/WEBP/HEIC/HEIF/PDF); anything else → `failed` with a
   message the list shows ("Not a photo or PDF").
2. PDF → `pypdfium2` renders page by page at 200 dpi; images → Pillow (`pillow-heif` registers
   HEIC), EXIF-transposed. Each page is normalised to a JPEG with the long side ≤ 2200 px,
   quality 85 — what the browser shows, what the decoder reads, what the model receives. ~500 KB
   a page; a 12 MP photo decodes to ~50 MB for the duration of one page and is dropped before the
   next.
3. The QR is decoded on the FULL-resolution page before it is shrunk (D3). Each page is saved as a
   `PaperPage` (`status=queued`) with its code, then `recognise_paper_page.delay(id)`.
4. The original upload is deleted from storage; `PaperUpload.status=split`, `pages_count` set.

Both wheels bundle their native library (`pypdfium2` ships pdfium, `zxing-cpp` ships the decoder,
`pillow-heif` ships libheif) — no apt line in the Dockerfile. The image is python:3.12-slim on
Debian trixie; the wheels are manylinux2014 and import cleanly there (checked in the task list).

### D3. The code is read locally, never by a model

Payload `MSFORM:<form>:<copy>:<page>:<pages>` (upper case so the QR uses alphanumeric mode;
`copy` 0 = printed without numbers); the first build's `ms:form:<form>:<page>:<pages>` still parses.
Two QR codes per page, in both bottom corners, 20 mm at error level H, drawn as vector squares —
one survives a thumb, a fold or a shadow over the other. `#<copy>` is printed top right and the
footer line reads `MS-<form> · #<copy> · Page n of N`, for a human matching paper to screen.

`survey/paper/codes.py::decode(img)`: zxing-cpp over the page scaled to ≤ 1800 px, then over 2×
crops of the bottom corners. Ingest calls it on the full-resolution image (a 200-dpi render or the
original photo); recognition calls it once more on the stored JPEG for a page without a code. A
page dropped into a response for a known page number (`expected_page`) takes that number when no
QR reads (`code_source='manual'`). Page 1 also carries the "answer online" QR
(`/surveys/<uuid>/?utm_source=paper&utm_medium=print_form`); a page dropped into a response whose
form code is out of frame but which shows that QR is page 1 of the response's form
(`codes.shows_first_page_link`) — the first live check was a page 1 of a single-QR form whose right
corner was cropped. Anything else without a code is set aside; on the response it was dropped into,
the warning offers "It is page [n]" + *Attach*. Checked on printed
PDFs: copies 141, 147 and 160 read correctly.

The first build's fallback — a vision call reading the footer text — is gone (owner rule: the page
number without AI). It also failed in practice: with `max_tokens=200` Gemini spent the whole budget
thinking and returned nothing.

### D4. Placement is deterministic: the code decides

`survey/paper/sheets.py::place_page(page)`, under a lock on the inbox:
1. **Numbered copy** → the response with that `copy` (unique constraint per inbox), created on
   first sight. An empty, open "New response" the page was dropped into takes the copy instead.
   Dropped into a different response → still goes to its own copy; the card it was dropped on
   lists "This photo is Copy 7, page 1 — it went there".
2. **No number, dropped into a response** → that response.
3. **No number, from a PDF of *Upload a stack*** → the response of that upload (`source_upload`):
   one PDF = one filled form.
4. **No number, a loose photo** → set aside: "add this photo to a response, or upload one PDF per
   filled form". Nothing can tell whose it is, so nothing is guessed.
5. Target stored/skipped, or a different printed form → set aside with the reason.
6. Same page number already on the response → the earlier page becomes `replaced` (later photo
   wins: a re-shot page is the usual case); *Restore* swaps them back.

Set-aside pages (`unrecognised`, reason in `error`) are listed on *Paper responses* with *Add to
response* (pick a response and the page number) and *Remove*; when exactly one open response
misses exactly one page, the list suggests it. A response is `recognising` while a page is queued,
`review` when it holds pages 1…N of its form, `incomplete` otherwise; `next_reviewable` serves
complete ones first, then incomplete ones with at least one read page.

Why not order + page number (the first build): two phones, a missed page or a re-shot page and the
grouping silently splits or merges respondents. The first live check produced two sessions from
one form.

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
  max_tokens=16000)` (Gemini counts thinking tokens against it); `AIGenerationEvent(kind='paper_page')` records usage and outcome, like a
  draft. `check_quota(organization, 'paper_page')` runs before the call — permissive today, the seam
  for a per-plan allowance tomorrow. A cap of 500 waiting images per inbox and 40 MB per file is
  not quota but sanity.
- `DOUBTFUL = 0.75`: a field below it, or `unreadable`, is doubtful. The response's `extraction` is
  the merge of its pages' fields by code (a later page never overwrites an earlier page's value
  for the same code — a question is printed once), `doubtful_count` the number of doubtful fields.

**Cost goes to PostHog at once** (owner, 2026-10-29): every extraction call emits `$ai_generation` through `product_events.emit_llm_generation` the moment the
`AIGenerationEvent` row is written, not at the end of the response: `$ai_span_name` = the event's
kind (`paper_page`; the helper stops hard-coding `survey_draft`), `$ai_trace_id` =
`paper-response-<response id>` so a response's pages roll up to one trace on the LLM Analytics dashboard,
`$ai_input_tokens` (Gemini counts the image in `promptTokenCount`, so the computed cost includes
it), `$ai_output_tokens` with thinking folded in as for drafts, latency, `$ai_is_error` on a
failure, plus `survey_id`, `response_id`, `page_number` — ids only. PostHog prices the tokens by
model; nothing in our database stores a dollar figure.

Thinking level: the extraction call sends `AI_THINKING_LEVEL` like a draft. Transient provider
errors retry twice with backoff in the task (the same classification the client already makes);
a final failure leaves the page `failed` with *Retry* in the list.

### D6. Review is page by page of the printed form, through the entry machinery

The owner's rule from the first live check (2026-10-31): the unit of review is the PHOTOGRAPH,
not the survey section — the eye reads the sheet and fills the field beside it, and a section
that runs over two pages must not become an endless scroll next to one picture. So:

`POST /editor/surveys/<uuid>/responses/paper/r/<id>/check/`:
- Creates the response's `SurveySession` if none: `survey` = the printed form's version header,
  `language` = the form's language, `source='paper'`, `entered_by`, `opened_by_kind` as item 1,
  `paper_sheet=sheet`. The header step of item 1 is skipped — the form code answered its three
  questions. Redirects to `…/r/<id>/pages/1/`; a form printed before the item map
  existed (no `items` in its layout) falls back to the section flow below.
- `paper_response_page(n)` (`paper_views.py`): `_page_plan` resolves `layout[n]["items"]` to
  `[(section, [codes])…]` in drawing order on the form's version header. The section with a geo
  question on the page (else the first) is the SHELL section — `_build_section_context(…,
  questions_filter=codes)` gives it the map, the geo widgets and `#section-data`; the other
  sections' questions ride in the same `<form>` as extra `SurveySectionAnswerForm`s
  (`questions_filter` again), each under its section title. POST calls `save_section_answers(…,
  only_questions=codes)` per section — the writer replaces ONLY the named questions, so a section
  spanning two pages keeps the other page's answers — then Next → `n+1`, Back → `n-1`, a stepper
  step → that page, Finish → Saved. Progress reads "Page n of N". A page with no question (a map frame alone) says so.
- Prefill: `sheet_prefill(sheet, questions)` into `_build_section_context(prefill=…)`, used as
  `initial` for questions that have no `Answer` row yet (a saved page's rows win). `sheet_prefill`
  speaks the dialect the existing `initial` dict speaks (choice → `str(code)`, multichoice → list,
  number → value, write-in → `other_option.field_name(code)`), so `SurveySectionAnswerForm` is
  untouched.
- **A missing page is attached from the review**: when the response has no image for page `n`, the
  pane shows the attach box (Take photo / choose files) instead of the picture; the file posts to
  the upload endpoint with `sheet` + `page_number`, `PaperUpload.sheet/expected_page` carry it,
  and placement (D4) decides: a page whose code will not read is taken for the expected number
  (`code_source='manual'`), a numbered page of another copy goes to its own copy. `paper_review.js` polls `…/pages/<n>/status/` and reloads when the page
  is read. The fields stay editable meanwhile — Next leaves the page blank.
- The section flow of item 1 (`entry_section` with `session.paper_sheet`) stays for old forms:
  it passes `prefill` and the page whose items include the section (`page_for_section`).
- The context also carries `paper_doubtful` (codes) and `paper_blank` (codes the model saw empty),
  rendered into `#section-data` as `data-paper-doubtful`/`data-paper-blank`; `paper_review.js`
  marks the field wrappers (`.paper-doubtful` amber, `.paper-blank` grey) and adds a count to the
  entry bar ("3 fields to check"). Nothing is auto-accepted silently: every section is shown.
- **The page pane**: `entry_section` picks the page whose `items` contain `section:<code>`
  (else the response's first page) and renders `editor/operator_entry/_paper_pane.html`: the image
  (served by `paper_page_image`, the gated private-tier stream used for comment attachments),
  zoom (CSS transform, wheel + buttons), rotate 90°, a page switcher over the response's pages, and a
  "Map" toggle on `map`-layout sections. On a `form`-layout section the pane takes the stage
  (the empty side of the layout); on a `map` section it overlays the map and the toggle swaps
  them — geo answers still need the map, item 4 will read marks from the same pane.
- Saving the last page → `entry_saved`: `mark_completed()`, `sheet.status='entered'`,
  `entered_at`, `delete_sheet_images.delay(sheet_id)`; the Saved page reads "Copy 7 stored" and
  its *Check next* opens `next_reviewable` or returns to *Paper responses* when none.
  `paper_sheet_entered` carries `fields_total`, `fields_doubtful`, `fields_changed` (diff between
  prefill and the stored answers, by code) — the quality signal for the prompt.
- *Delete* on an open response (`sheets.delete_sheet`): pages, images, the unfinished session
  (trashed), the row — the copy number is free again. "Skipped" (a row kept without images) held the
  copy number and made re-uploading impossible (owner, 2026-11-01); stored responses are deleted on
  Responses.

### D7. One page, *Paper responses*; uploads stream to storage; the list polls

- `/editor/surveys/<uuid>/responses/paper/` (`paper_home`): per printed form, copies printed and
  back (from `PrintRun` ranges vs responses' `copy`); *New response* (POST → an empty response, its
  page opens); *Upload a stack*; *Check next*; open responses as cards with one slot per page
  (missing / being read / read / doubtful / failed); set-aside photos; uploads in flight or failed;
  the last 20 stored. `…/paper/r/<id>/` is one response: its slots with thumbnails, a drop zone
  that posts with `sheet`, replaced photos with *Restore*, photos that went elsewhere, *Check* /
  *Skip*. Entry point: *Enter a response ▾ → From photos of paper forms* on Responses, and a link in
  the operator entry header. Same gate as item 1 (`entry_gate`).
- `POST …/paper/upload/` takes ONE file per request, 40 MB max, creates `PaperUpload` with the next
  `seq`, saves the `UploadedFile` straight into the `FileField` (Django has already streamed anything
  over 2.5 MB to a temp file), enqueues `ingest_paper_upload` on commit, answers `{id, seq}`.
  `js/paper_upload.js` sends the selected files one after another with XHR progress, has *Take
  photo* (`capture="environment"`) next to *choose files*, and keeps the zone live.
- The lists re-render through HTMX every 3 s while an upload or page is in flight
  (`paper_home_list`, `paper_response_slots`), like the dashboard's import jobs.

### D8. Images live until the response is done; the sweep takes the rest

- `delete_sheet_images(sheet_id)` deletes the pages' images (rows stay with `image=''`) when a
  response is stored or skipped.
- `sweep_paper_batches` (dry run by default, `--delete` to act; run from `reclaim.sh`): deletes open
  responses whose `last_activity_at` is older than `PAPER_BATCH_TTL_DAYS=30` whole; deletes
  set-aside page images and originals older than that. Stored responses stay.
- `/trust/`: photos of paper forms are kept until the response is stored or for 30 days, whichever
  is first; the model provider receives the page image for the duration of the call.

### D9. `complete_structured` takes images

`LLMProvider.complete_structured(..., images=None)` — a list of `(mime_type, bytes)`. The Gemini
implementation puts each as an `inline_data` part before the user text; the Anthropic
implementation as `image` content blocks. Omitted → the payload is byte-for-byte what it is today
(the existing request-shape tests stay green). `survey/ai/client.py` stays the only module that
knows the wire format.

### D10. Numbered copies print in one pass

`build_form(..., copies=N)` lays the form out ONCE. `_CopiesCanvas` (a reportlab `Canvas`) turns
every body page into a Form XObject (`beginForm`/`endForm`); `save()` then emits, for each copy and
each page, `doForm(body page)` + the page chrome + that copy's codes (two QR, footer line, `#copy`).
The body — text, map frames, fonts — is stored once; 20 copies × 10 pages ≈ 1.5 MB in ≈ 3.9 s, of
which ≈ 2.3 s is the layout (gunicorn timeout 60 s). Tried and dropped: pypdf `merge_page` over a
shared page object (each copy accumulated every earlier copy's stamps, and reversing the order was
slow), and pdfium XObjects (12 MB and a finaliser assert). `LAYOUT_VERSION = 2` enters the
structure hash, so forms printed before the two-QR footer are a different `PrintedForm`.
`?mode=copies&copies=N` (1…200) or `mode=single`; the filename names the range
(`…-copies-<first>-<last>.pdf`); `form_printed` carries `copies`. The Share dialog says how many
were printed and where the next print starts, and that a photocopy repeats its number.

### D11. Marks on the printed map → coordinates (epic item 4, `survey/paper/marks.py`)

The same page call that reads the fields reads the map: the message lists the frame section's
geo questions with their legend letters (`structure.mark_letters`, the one function paper and
reader share) and the readable sub-questions of their tables; the model returns `marks`
(label, question, vertices in 0–1000 of the photo, confidence, the row's `answers`) and
`map_frame` (its box). Registration is local: `find_alignment_squares` (Pillow, pure Python —
per corner a dark, solid, square blob of ~3 % of the short side, the corner-most one; the QRs
are too big and not solid, text too small and not solid) and a 4-point homography photo →
page mm (`PAGE_MM`, square centres 11 mm in). Fallback when a square is out of frame: the
model's frame box → the frame rectangle. Then `mm_to_lnglat`: a fraction of the printed frame
rectangle (recorded at print time) → a world pixel between `project(west, north)` and
`project(east, south)` at the frame's zoom → `unproject`. Linear in world pixels, not in
degrees, because the static map is a Mercator image. Features take the shape
`existing_geo_answers` restores (`properties = {question_id, sub_code: [values]}`), so the map
of the check shows them as it shows stored answers, and the section POST stores what the
operator kept. One rule for pages: a section's geo questions belong to the page with its frame
and to no other page (`_page_plan`), or an empty POST of the heading's page would wipe the
placed marks. Tried in thought and dropped: a vision call per mark (cost), the model computing
coordinates itself (it cannot), ignoring perspective (a phone shot at 20° puts a dot 8 mm off).

**Registration, after the second live check** (owner, 2026-11-01: "the dots were not placed well;
maybe the map needs its own fiducials"): three causes, three fixes. (1) The page squares were all
in the photo but the bottom-right one merged with the table's shadow at a soft threshold —
`_square_in` now tries thresholds strict → loose and sizes squares against a page that may fill a
third of the photo. (2) The model centred a dot on the "• A1" group; the prompt now says the
symbol's ink only. (3) The owner's fiducials: four 5-mm squares printed in the margins beside the
frame (5 mm outside its left/right edges, level with top/bottom — ON the corners they merged with
the border and the grid), recorded as `fiducials` / `fiducial_dx_mm` in the frame record, found
around the model's frame box and preferred over the page squares (closer to the marks, no paper
curl, there on a photo cropped to the map). **Bent paper** (owner, 2026-11-01: "we will not be working with ideal photos"): a page on a lap is
no plane, and the best plane through the landmarks still left a dot 2–3 mm off in the middle of
the frame. Two answers. The frame gets fiducials halfway down each side too (`fiducial_mids`,
`LAYOUT_VERSION = 4`) — a hand-held page bends along its long axis, and those two marks sample the
middle. And `fit_registration` adds a thin-plate-spline correction to the homography: the
residual at every landmark (near zero at a fiducial, up to a centimetre at a far page corner on a
bent page) is interpolated and added back, regularised per landmark by its weight, so the map is
bent the way its marks are. On the simulated bent page (12-px sideways slide, perspective, dark
table) the plane missed by millimetres and the correction lands every probe within 1 mm; on a flat
page the residuals are below 0.3 mm and no correction is fitted. **The frame's border and the map
itself** (owner, 2026-11-01: "the dots flew off again — I need the right algorithm, not a dot placed
by hand"): on the lap shot of copy 165 the bottom-right fiducial was out of frame, so the border is
sampled all around (`find_frame_edges`, seven samples a side along the normal, ×10) and its corners
come from the fitted lines (×30) — that brought the border to 0.3 mm and left A2 5.5 mm off: the
page bows INSIDE the frame, which no border can see. The only thing inside the frame whose place on
the paper is known is the map that was printed there, so the frame image is kept at print time
(`texture.save_reference`, `paper_refs/<form>-<page>.png`, `ref_key` in the record; a form printed
before it was kept is re-rendered, the grid stand-in never) and `survey/paper/texture.py` matches
it: the photo is rectified into the reference's grid through the current registration (its inverse
by fixed-point iteration on a coarse grid), reference patches (64 px at 5 px/mm) are searched
±28 px around a 6×4 grid of anchors by FFT normalised cross-correlation (summed-area tables for the
window statistics — a sliding-window view cost 50×), a peak on the window's rim is rejected, and
every match is a landmark (×20) the spline follows. Three rounds at most: the registration the
first round informed rectifies the photo for the second, so a bend the first window clipped is
within reach. One trap on the way: an edge sample pins the paper ACROSS its side, but along it it
only repeated what the first plane predicted, and 25 of them outvoted the interior; every refit now
re-anchors them along their side from the current fit (`_fit_with_edges`). A2 on the lap shot:
5.5 mm → 0.4 mm, the whole frame aligned in an overlay; 2.5 s a page. **The dot's ink** (copy 166, the
next upload: the map aligned to 0.2 mm and A1 was 4.3 mm off — the model had answered with the
label again, prompt or no prompt): once the photo is registered, the ink is simply the rectified
photo minus the reference, so `texture.snap_to_ink` looks within 7 mm of the model's point for a
compact blob 0.8–4.5 mm across with discness ≥ 0.5 (its area over the circle around its box — a disc
is near 1, a serifed "1" 0.3, an A 0.4; a fill-and-aspect test let the "1" of the synthetic label through) and moves the vertex to the nearest; nothing dot-like → the model's
vertex stands. **Then the owner asked the larger question** (2026-11-01: "doesn't it seem the map
needs no AI at all? an analytical module?") and the answer is `survey/paper/ink.py`, the hybrid:
the geometry is read off the registered photo and the model only names it. Finding the ink took
four wrong turns, each a lesson. HSV saturation showed the strokes on one copy and painted the
whole page on the other: it is a ratio, so JPEG noise on near-black print and a warm lamp's tint
both count. Absolute chroma: the pen on copy 165 is a faint blue-grey, under 20 counts. Chroma
against the local paper colour: still nothing for a black pen. Darkness alone: every street name
a pixel off its print. What holds on both copies is two readings joined, each against the paper
and the print AROUND the pixel: (a) a coloured pen — each channel's share of the pixel's
brightness less its 8-mm mean (a warm lamp shifts the whole page alike, a shadow has the paper's
colour), a little darker than the paper, darker than the darkest print within 3 px (JPEG chroma
subsampling smears a stroke's colour over a 2-mm block, and a printed line inside it took the ink's
colour), on light print; (b) a black pen — darker than the paper's 8-mm mean by 50 (a pen is 80–150,
the edge of a shadow under 48) AND than its 3-mm mean by 30 (a shadow is a gradient, a stroke a
step) AND than the darkest print within 3 px by 40; neither on near-black print (the scale bar, a
route shield). No morphological opening — a 0.5-mm stroke is 2–3 px at 5 px/mm and an opening
erases it; specks go with a 12-px component floor. Components of that mask are read in the
order that keeps the easy cases from eating the hard ones: hatched clusters first on the raw
strokes (≥ 5 short strokes within 1.5 mm: a spray area, its own pixels as the cloud), filled discs
next (0.8–3.2 mm, discness ≥ 0.5 — a thick pen's "A" is a 4-mm blob and is not), then the rest is
bridged (closing r = 2: a ballpoint skips) and read as a loop with a hole ≥ 3 mm² (an area; a
coin-sized round one is weak), a dense blob far thicker than a stroke (a scribbled area), a long
single-path stroke (a line; glyph-sized pieces are weak), or writing. Line pieces whose ends lie
within 8 mm are sewn; a sewn line whose ends meet is an outline. What no rule can tell apart is a
10-mm "A2" from a 10-mm stroke, so the pairing with the model's marks decides (`marks._match_marks`:
median distance of the model's vertices to the ink, 25 mm for a strong piece, 8 for a weak one;
further strong pieces along one model line are sewn onto it — the route whose pen lifted twice) and
the model's new `label_box` excludes ink under the handwritten label outright. Ink with no model
mark is still a mark — numbered, at confidence 0.5, for the operator to confirm — because the model
dropped A1 of three on a re-read; a model mark with no ink keeps its vertices at 0.6. On copy 165
that gave the three routes (A2 drawn as two dashes), the circle C, the hatched D and the line B
from the ink alone. `find_alignment_squares` rejects four squares that do
not form a portrait quadrilateral, or the fiducials of a cropped photo would pass for page corners;
it works at full resolution and checks a blob is solid through, because on the 900-px copy of a
photo whose bottom-right page corner was cut off, the centre of a QR finder pattern (the same size
and fill at that scale) passed for the missing square and skewed every mark north-east. For forms
printed before the fiducials the model is asked for the frame's four CORNERS (`map_frame_corners`,
a trapezoid on a tilted photo) and `_frame_quad` registers through them before falling back to the
box — on page 7 that put the three dots within a few hundred metres of the ink.
`LAYOUT_VERSION = 3`.

**A table that runs onto the next page** (Stack #263): copy 165 was printed before keep-together,
and its SPOT table's A2–A3 rows fell on page 3 under the ROUTE map, where the reader asked the model
only about ROUTE — and a long table splits that way with keep-together too. The printer already
records what is needed: a geo question's own block follows its table on paper, so the page of its
`question:<code>` marker is the page the table ends on, and every page from the frame's to that one
carries rows. `extract.table_items_for_page` lists those questions for a page, the message gets a
"table rows continued" block (rows as marks with no points — the same schema), `marks.table_rows`
keeps them as a `rows_only` field, `merge_pages` hangs them on the map page's field as `rows_extra`
(an earlier page still wins the field itself), and `_paper_map_context` gives each row's answers to
the mark of the same label, or lists the row as `unplaced`: the check draws it with its cells filled
and a "place it on the map" link, so nothing written in the table is lost for want of a mark.

**A re-shot page** (owner, 2026-11-01: "I shot it on the table — same result"): the table shot
had been read correctly, but the page showed the answers Next had stored from the lap shot,
because stored rows always win over the extraction. `review.supersede_machine_answers`, called by
`recognise_paper_page` when the page replaces an earlier one, deletes the stored rows that still
equal the EARLIER reading's values (coordinates to 5 decimals, codes, text) and keeps every row the
operator changed — the operator's work survives, the machine's first guess does not.

**The map page of the check reads like the paper** (owner, 2026-10-31, `map-page.mockup.html`):
the respondent panel with its draw buttons and pop-ups was the wrong tool for the operator — a
420-px column beside a map hidden behind the photo. Now the page is `survey-form-layout` (photo
left, page right, half and half; `paper_map_mode` overrides the section's layout classes and
`data-layout`), and the right side is `_paper_marks.html` + `js/paper_marks.js`: the printed
frame as its own Leaflet map (`zoomSnap: 0` so `fitBounds` lands on the frame exactly; the
respondent basemap cloned from `window._basemapLayers`), then per map question the table the paper
has — rows A1…An from `_marks_count`, the sub-questions as columns — with Show (→
`window.PaperReview.focusBox(feature_boxes[i])`), remove, *place it on the map* (`L.Draw` for
lines and areas) and *Add a mark*. The geo questions leave the forms (`questions_filter` minus
geo codes); a hidden `<input name="<code>">` per question carries `feature|feature` with
`properties = {sub: [values]}`, i.e. what `save_section_answers` already parses, re-serialised
after every change. Stored rows win over read ones on a re-render (`views.geo_answer_features`,
the one builder of the `existing_geo_answers` shape, now shared). The printed table gets its
boxes in every row (`pdf._sub_cell`): the header-only boxes left nothing to tick.

## Risks / Trade-offs

- **Model reads a checkbox wrong with high confidence** → the review shows every section, not just
  doubtful fields; `fields_changed` in `paper_sheet_entered` measures how often, and the help page
  says what the model is good and bad at (ticks vs. crosses, handwriting). Mitigation in the
  prompt: "a box is marked when it has any ink inside; a struck-through mark is not an answer".
- **A page photographed twice** → same copy, same page: the later photo wins and the earlier is
  `replaced`, restorable from the response page. Nothing is dropped silently.
- **One numbered copy photocopied for many respondents** → the copies share a number. The Share
  dialog says so; such stacks go through *New response* or one PDF per form.
- **A code naming another survey's form** → the form id must name a printed form of THIS survey,
  or the page is set aside.
- **Worker memory with big PDFs** → one page rendered at a time, original deleted after the
  split; the Celery worker is a separate service with its own memory. A 300-dpi A3 scan still
  decodes under 100 MB.
- **S3 round trips per page** (save JPEG, read for the model, stream for the pane) → each is one
  object; the pane image is cached by the browser (`Cache-Control: private, max-age=3600`) since
  the URL is per page.
- **Forms printed before this change** → no `items` map and no copy number: whole structure per
  page, the section flow, and New response / one PDF per form. Acceptable: the feature ships days
  after printing did.
- **`entry_section` grows a second prefill source** → kept to one keyword argument
  (`prefill`) and one helper (`sheet_prefill`); the `Answer`-based `initial` code is not touched.

## Migration Plan

1. Migration `0113`: `PrintRun`, the four paper models, `SurveySession.paper_sheet`,
   `AI_GENERATION_KIND_CHOICES` + `paper_page` (choices change only). Additive; no backfill.
   `PrintedForm.layout` gains `items` on the next print; old rows are read with the fallback.
2. Requirements: `pypdfium2`, `pillow-heif`, `zxing-cpp` (and `pypdf` moved to runtime) in the
   Pipfile; rebuild the image.
3. Settings: `PAPER_UPLOAD_MAX_BYTES`, `PAPER_BATCH_MAX_PAGES`, `PAPER_BATCH_TTL_DAYS`,
   `PAPER_DOUBTFUL_CONFIDENCE`.
4. `reclaim.sh` runs `sweep_paper_batches --delete`.
5. No kill switch (owner rule): the feature is behind the Pro gate and the entry point; a
   rollback is a revert.

## Open Questions

- Allowance number for `paper_page` per workspace per month — the seam is called with a kind;
  the number is a pricing decision (none yet, as for drafts).
- Whether the Anthropic provider needs image support at all now (`AI_PROVIDER` is Gemini in
  production); implemented for interface symmetry, tested only at the payload level.
