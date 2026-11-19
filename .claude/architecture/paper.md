# Printable paper forms and paper responses from photos

Moved verbatim from `CLAUDE.md` (change `claude-md-diet`). `CLAUDE.md` keeps the one-line rules; this file keeps the detail. Update it in the PR that changes the behaviour.

**Printable paper form (`survey/print/`, change `printable-form`, #489; epic #350 item 2)**: the
Share page's *Print a paper form* (every status, every plan, `editor` role) downloads
`/editor/surveys/<uuid>/print/form/?lang=&paper=` — `pdf.build_form` walks the RESPONDENT structure
(`compute_visibility(surface='respondent')`, `group_runs`; operator-only items left out, rules as an
"Answer only if …" line) and renders one `QUESTION_SHAPES[input_type]` flowable per question in
reportlab (pure Python; the bundled DejaVu fonts in `survey/print/fonts/` cover everything but CJK).
A map section prints a frame from `static_map.render_frame`: the Mapbox **Static Images** API for the
basemap (same token, a separate metered SKU, cached a day per frame, fail-soft to a gridded empty
frame) with the survey's reference layers drawn on it by Pillow, then a letter legend (A ●, B ━,
C ▭, D ░ — never icons: they do not survive a photocopy) and a sub-question table per mark. Every
page carries four 6 mm alignment squares and a **form code** — two vector QR (20 mm, level H, both
bottom corners) with payload `MSFORM:<form>:<copy>:<page>:<pages>` (copy 0 = unnumbered; the old
`ms:form:…` still parses, `print/form_code.py`) and the line `MS-<form> · #<copy> · Page n of N` —
that names a `PrintedForm` row — version, language, paper,
`structure_hash`, and per page the map frame's rectangle in mm plus its geographic bounds — which is
what item 4 (photo marks → coordinates) will read; a reprint of an unchanged survey reuses the row.
Fixed form strings come from the RESPONDENT catalogs (75; `test_every_printed_form_string_is_translated_in_every_catalog`),
the dialog's from the creator ones. Event `form_printed` is server-side. The flyer generator #220
is the next consumer of the same page template and static map. `PrintedForm.layout[page]["items"]`
(since change `paper-photo-entry`) lists what starts on each page — `ItemMarker` flowables record it at
draw time — so a photographed page is read against exactly those questions; the walk both share is
`survey/print/structure.py::plan_items`. **Numbered copies** (`?mode=copies&copies=N`, 1…200, the
dialog's default; `mode=single` = one copy to photocopy): `PrintRun` hands out copy numbers per
CANONICAL survey under `select_for_update` on its header — they only grow, across forms, languages
and papers, so a copy number names one questionnaire forever. The form is laid out once;
`_CopiesCanvas` stores each body page as a Form XObject and stamps every copy's codes over a
`doForm` (20 copies ≈ one copy in bytes). Never print copies by re-running the layout or by merging
PDF pages: both were tried and were slow or huge. `LAYOUT_VERSION` in `pdf.py` enters the structure
hash — bump it when the page chrome changes. `?keep=1` (the dialog's default) wraps a map section's
heading, frame, legend and marks tables in one `KeepTogether` and is part of the hash too; file
questions are not printed at all (`structure.plan_items` drops `FILE_INPUT_TYPES`).

**Paper forms from photos (`survey/paper/`, `survey/paper_views.py`; change `paper-photo-entry`, #495;
epic #350 item 3)**: *Responses → Enter a response ▾ → From photos of paper forms* opens **Paper
responses** (`/editor/surveys/<uuid>/responses/paper/`, the operator-entry gate). The operator's unit
is the **paper response** (`PaperSheet`, labelled "Copy 37" / "Response 4" by `.label` — no surface
says sheet or batch); `PaperBatch` is a hidden per-survey inbox (`paper.inbox_for`) that only holds
counters. Rows: `PaperUpload` (one file as received, plus where it was dropped: `sheet`,
`expected_page`, `is_pdf`), `PaperPage` (one JPEG ≤ 2200 px on the PRIVATE tier with its code),
`PaperSheet`, `SurveySession.paper_sheet`. **The code decides, never the order of arrival**
(`survey/paper/sheets.py::place_page`): a numbered copy's page goes to that copy's response (unique
per inbox) whatever card it was dropped on; an unnumbered page goes where the operator put it (*New
response*) or to its PDF's response (one PDF = one form); a loose unnumbered photo, a page of a stored
response or of another form is set aside with a reason; a second photo of the same page wins and the
first is `replaced` (restorable), and once the new photo is read `review.supersede_machine_answers` drops the stored rows that still equal the earlier reading (the operator's edits stay). The first build grouped by upload order and split one form into two
sessions — do not bring order-based grouping back. **No model ever reads a code**: zxing-cpp decodes
it locally, at full resolution in ingest (PDF at 200 dpi) and once more on the stored JPEG. **The web
process never decodes a byte**: the upload view hands the file to storage and enqueues
`ingest_paper_upload`; `survey/paper/ingest.py` and `recognise_paper_page` (place, then
`check_quota(org, 'paper_page')`, then ONE vision call per page bounded by the page's `items`,
`extract.py` + `prompts.py`) run in Celery — on the dev stack the worker does not reload, restart it
after touching this code. Gemini counts thinking tokens against `max_tokens` (extraction uses 16000; a
200-token call came back empty). `LLMProvider.complete_structured(images=[(mime, bytes)])` is the only
way an image reaches a provider. Every call is an `AIGenerationEvent(kind='paper_page')` and an
immediate `$ai_generation` (trace `paper-response-<id>`, `survey/paper/accounting.py`) — PostHog
prices it; nothing stores dollars. The check is page by page of the PRINTED form
(`paper_response_page`): photo left, the questions printed on that page right (`_page_plan` over
`layout[n]["items"]`, `questions_filter`, `save_section_answers(only_questions=)` so a section split
over two pages keeps both halves), a stepper, prefill through `_build_section_context(prefill=…)`
(stored rows always win), doubtful (`confidence < PAPER_DOUBTFUL_CONFIDENCE` or `unreadable`) and
blank fields marked, a missing page attached in place; forms without an item map fall back to the
section flow of operator entry. **Marks on the printed map (item 4, `survey/paper/marks.py`)**: on a
page with a map frame the same call lists the frame section's geo questions with their legend letters
(`print/structure.py::mark_letters`, shared with the printer) and returns `marks` (label, question,
vertices in 0–1000 of the photo, the table row's answers) plus `map_frame`; registration is LOCAL —
`find_frame_fiducials` (the 5-mm squares printed in the margins beside the frame: corners since
`LAYOUT_VERSION = 3`, mid-sides too since 4; `fiducials`/`fiducial_dx_mm`/`fiducial_mids` in the frame
record, targets from `fiducial_targets`) first, then
`find_alignment_squares` (page corners, pure Pillow at full resolution, thresholds strict → loose,
solid through — a QR finder centre is not a square — and a portrait quadrilateral), then the model's
`map_frame_corners` (a trapezoid), then its box; one weighted least-squares homography over every
landmark (`fit_registration`: fiducials ×50 when ≥ 3, else ×4; page squares ×1; the frame's border
sampled all around by `find_frame_edges` ×10 and its corners from the fitted lines ×30) PLUS a
thin-plate spline over the residuals, because paper on a lap is not a plane — `apply()` takes the
`{h, tps}` registration. A page also bows INSIDE the frame where no border can see it, so the
printed map is the last landmark: `survey/paper/texture.py` matches patches of the frame image kept
at print time (`texture.save_reference` → `paper_refs/<form>-<page>.png` on the private tier,
`ref_key` in the frame record; forms printed before it re-render, the grid stand-in never) against
the photo rectified through the current registration (FFT normalised cross-correlation at a 6×4
grid of anchors, ×20, up to three match → refit rounds in `_refine_with_interior`); edge samples
are re-anchored along their side on every refit (`_fit_with_edges`), since across the side they
pin the paper and along it they only repeat the plane they were found with. For a `point` question
the vertex is then moved onto the ink (`texture.snap_to_ink`: rectified photo minus reference, the
nearest blob 0.8–4.5 mm within 7 mm with discness ≥ 0.5; letters fail it) — the model answers
with the label beside the dot often enough that its vertex is a hint, not the answer. **The hybrid
(`survey/paper/ink.py`)**: with a reference image the GEOMETRY of every mark comes from the ink —
coloured against the paper around it (a blue pen: channel shares less their 8-mm mean) or darker
than the paper's 8-mm and 3-mm means and than the darkest print within 3 px (a black pen), never on
near-black print — not HSV saturation, not absolute chroma, not darkness alone (each failed on one of
the two copies; `design.md`) — its components read as hatched cluster → spray, filled disc → point, closed loop → area,
long stroke → line (pieces sewn across skips, an outline whose ends meet closed), glyph-sized rest →
writing — and the model only NAMES them: `_match_marks` pairs each model mark with the ink of its
kind along its vertices, ink the model missed becomes a numbered mark at confidence 0.5, a model
mark the ink lacks keeps its vertices at 0.6, and ink under the model's `label_box` is writing.
Never make the model's vertices the geometry again where ink is available. `mm_to_lnglat` goes
through the frame record's Mercator bounds (linear in world pixels, never in degrees). The
prompt asks for the symbol's ink, never the label beside it. The result is GeoJSON features in the `existing_geo_answers` shape, which
`_build_section_context` restores onto the map from `prefill` (never into `initial`), and
`_page_plan` gives a section's geo questions to the page with its frame and to NO other page — an
empty POST of the heading's page would wipe the placed marks. That page (`paper_map_mode`) is NOT the
respondent panel: form layout half and half, `_paper_marks.html` + `js/paper_marks.js` draw the
printed frame as their own Leaflet map and the marks TABLE the paper has (rows A1…An, the
sub-questions as columns), and a hidden input per geo question posts `feature|feature` in the dialect
`save_section_answers` parses (`views.geo_answer_features` is the one builder of that feature shape).
On paper, `pdf._sub_cell` prints a choice column's boxes in EVERY row. A table that runs onto the
next page (`extract.table_items_for_page`: the frame's page up to the page of the question's own
`question:<code>` marker, which follows the table on paper) is asked for there as rows without
geometry (`marks.table_rows`, a `rows_only` field); `merge_pages` hangs them on the map page's field
as `rows_extra` and `_paper_map_context` joins them to the marks by label — a label with no mark is an
`unplaced` row the check shows filled, with a place-it link. Images go when a response is
stored (`delete_sheet_images`) or the response is deleted (`sheets.delete_sheet`: an open response goes whole, its copy number free again — there is no "skipped"), and by `sweep_paper_batches --delete` (in `reclaim.sh`, deletes
open responses idle past `PAPER_BATCH_TTL_DAYS` the same way; stored rows stay). Export column `paper_copy`. Events:
`paper_response_created`, `paper_page_recognised`, `paper_sheet_entered` (`fields_changed` vs the
prefill = the reader's quality signal) — ids and counts, never content.
