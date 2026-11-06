## 1. Dependencies and settings

- [x] 1.1 Add `pypdfium2`, `pillow-heif`, `zxing-cpp` to the Pipfile with one comment each (why a wheel, no apt line); relock; install into the worktree venv; verify all three import on python:3.12-slim (trixie) in a throwaway `docker run` of the built image
- [x] 1.2 Settings `PAPER_UPLOAD_MAX_BYTES` (40 MB), `PAPER_BATCH_MAX_PAGES` (500), `PAPER_BATCH_TTL_DAYS` (30), `PAPER_DOUBTFUL_CONFIDENCE` (0.75), each read from the environment with a comment on what it bounds
- [x] 1.3 `AI_GENERATION_KIND_CHOICES` + `paper_page`; `quota.check_quota` documents the second kind

## 2. Models and migration

- [x] 2.1 `PaperBatch`, `PaperUpload`, `PaperPage`, `PaperSheet` in `survey/models.py` per design D1 (private media storage keys `paper_uploads/<uuid>`, `paper_pages/<uuid>.jpg`; `seq` counters; `pinned`; `extraction` JSON; status choices); `SurveySession.paper_sheet` (SET_NULL)
- [x] 2.2 One migration (additive); `PrintedForm.layout` shape comment updated for `items`
- [x] 2.3 Admin registration (read-only list for support: batch, sheet counts, states)

## 3. Printed form records its items per page

- [x] 3.1 `survey/print/pdf.py`: `ItemMarker` zero-height flowable recording `section:<code>` / `group:<code>` / `question:<code>` into `records[page]['items']` at draw time, dedupe on re-draw; emitted before every section heading, group heading and question block
- [x] 3.2 Factor the item walk (`plan`) into `survey/print/structure.py::plan_items(survey, language)` used by `build_form` and by extraction
- [x] 3.3 Tests in `test_printable_form.py`: items per page for a two-page form; a map page carries both `map` and `items`; a form with no items on page 2 (map only) still has the key

## 4. LLM client takes images

- [x] 4.1 `LLMProvider.complete_structured(..., images=None)`; Gemini `_payload` adds `inline_data` parts (base64) before the text part; Anthropic adds `image` blocks; docstring on the wire shapes
- [x] 4.2 Tests in `test_ai_survey_generation.py`: Gemini body with one JPEG; body without images byte-identical to the current fixture; the fake provider used by other tests accepts the keyword

## 5. Ingest and codes (worker)

> Superseded by section 13 (v2, owner 2026-10-31); kept as the record of the first build.

- [x] 5.1 `survey/paper/ingest.py`: sniff type from bytes; PDF via `pypdfium2` page by page at 150 dpi; images via Pillow (+`pillow-heif`), EXIF transpose; normalise to JPEG ≤ 2200 px q85; `PaperPage` rows with consecutive `seq`; delete the original; `PaperUpload` status + `pages_count`; failures recorded with a plain message
- [x] 5.2 `survey/paper/codes.py::read_code(image_bytes)`: `zxing-cpp` over the page and over 2× corner crops; parse with `form_code.parse`; return `(form_id, page, pages, source)` or None
- [x] 5.3 Fallback `read_code_with_model(image_bytes)`: tiny vision call (schema `{code}`), `form_code.parse` tolerance; `code_source='text'`
- [x] 5.4 Tasks in `survey/tasks.py`: `ingest_paper_upload(upload_id)` (idempotent: a row past `queued` returns), `recognise_paper_page(page_id)` (code → placement → extraction; transient provider errors retried twice with backoff), `delete_sheet_images(sheet_id)`
- [x] 5.5 Tests (`survey/tests/test_paper_photo_entry.py`, eager tasks like `_eager_import`): a PDF printed by `build_form` and rendered through `pypdfium2` round-trips its QR on every page; an EXIF-rotated JPEG is upright; HEIC converts; `.docx` fails cleanly; a 6000 px image is bounded

## 6. Placement into sheets

> Superseded by section 13 (v2, owner 2026-10-31); kept as the record of the first build.

- [x] 6.1 `survey/paper/sheets.py::place_pages(batch)`: unplaced pages in `seq` order up to the first `queued`; new sheet on page 1 or when the last sheet cannot be continued; `review` vs `incomplete`; `pinned` pages untouched; `missing_pages(sheet)` for the list
- [x] 6.2 `move_page(page, sheet | None)` and `remove_page(page)` with re-evaluation of the sheets touched
- [x] 6.3 Tests: the four grouping scenarios of the spec; a duplicated page starts an incomplete sheet; a moved page survives a later placement pass

## 7. Extraction

- [x] 7.1 `survey/paper/extract.py`: items for a page from `layout[page]['items']` (fallback: all items + "return only what the page shows"); item description per question type in the form's language (code, type, name, options with codes and labels, write-in flag, bounds, max); excluded types; the response schema; `DOUBTFUL`
- [x] 7.2 `survey/paper/prompts.py`: system and user text (ink inside a box = marked; struck-through = not an answer; transcribe handwriting as written; `unreadable` when in doubt; never invent)
- [x] 7.3 `extract_page(page)`: `check_quota(org, 'paper_page')` → `complete_structured(images=…)` → typed values validated against the items (unknown option code → doubtful) → `page.extraction`; `AIGenerationEvent(kind='paper_page')` with usage and outcome; `merge_sheet(sheet)` → `sheet.extraction`, `doubtful_count`
- [x] 7.4 `product_events.emit_llm_generation(event, trace_id=None, span_name=None, extra=None)`: span name from `event.kind` (drafts keep `survey_draft`), trace `paper-batch-<id>`, `survey_id`/`batch_id`/`page_number`; called right after the `AIGenerationEvent` row is written for every `paper_page` and `paper_code` call, success or failure
- [x] 7.5 Tests with a stub provider: items sent for a page; geo not asked; typed values; doubtful count; old form fallback; provider 503 ×3 → `failed`; `AIGenerationEvent` per call; `$ai_generation` captured per call (success and failure) with the span, trace, tokens and no content property; the draft's `$ai_generation` unchanged

## 8. Batch pages, upload and status

> Superseded by section 13 (v2, owner 2026-10-31); kept as the record of the first build.

- [x] 8.1 URLs under `/editor/surveys/<uuid>/responses/paper/`: list, `new/` (POST), `<batch>/`, `<batch>/upload/` (POST), `<batch>/status/`, `<batch>/close/` (POST), `<batch>/pages/<page>/image/`, `<batch>/pages/<page>/move/`, `<batch>/pages/<page>/remove/`, `<batch>/pages/<page>/assign/`, `<batch>/pages/<page>/retry/`, `<batch>/sheets/<sheet>/enter/` (POST), `<batch>/sheets/<sheet>/skip/` (POST); all under `entry_gate`
- [x] 8.2 `survey/paper_views.py`: upload view saves the `UploadedFile` into the `FileField` without reading it, `select_for_update` on the batch for `seq`, 413/409 answers, enqueue; status JSON; image view streams from the private tier with `Cache-Control: private, max-age=3600`; move/remove/assign/retry
- [x] 8.3 Templates `editor/paper/batches.html`, `batch.html`, `_sheet_list.html` (HTMX partial), `_sheet_card.html`; counts; groups (uploads in flight, sheets, not recognised); *Review*/*Continue*/*Skip*/*Close batch*; page thumbnails
- [x] 8.4 `js/paper_batch.js`: drop zone + file input (`multiple`, `accept` images/PDF, `capture` hint on phones), queue with 3 in flight, XHR progress per file, one retry, poll `status/` every 3 s while in flight and swap the list partial; drag a page between sheets (SortableJS, long-press on touch) → `move/`
- [x] 8.5 Responses header: *Enter a response* becomes a two-item dropdown (*Type in a response*, *From photos*); locked variant unchanged; entry header gets the *From photos* link
- [x] 8.6 Tests: gate (editor/viewer/Free); another survey's batch 404; upload creates rows in order and enqueues; 413; 409 on closed; status payload; image gated; move/remove/assign

## 9. Review through the entry form

- [x] 9.1 `views._build_section_context(..., prefill=None)`: `prefill` values fill `initial` for questions without an `Answer` row; untouched otherwise
- [x] 9.2 `survey/paper/review.py::sheet_prefill(sheet, section)` → `(initial, doubtful_codes, blank_codes)` in the `initial` dialect (choice `str(code)`, multichoice list, number, text, write-in via `other_option.field_name`)
- [x] 9.3 `sheet_enter` view: create the session from the printed form (version header, language, `paper`, `entered_by`, `opened_by_kind`, `paper_sheet`), redirect to the first section without answers; `entry_section` passes `prefill`, `paper_doubtful`, `paper_blank`, the page for the section and the sheet's pages into the context
- [x] 9.4 `editor/operator_entry/_paper_pane.html` + `css/paper_review.css` + `js/paper_review.js`: image with zoom (wheel/buttons), rotate, page switcher; takes the stage on `form` layout, overlays the map with a toggle on `map` layout; marks `.paper-doubtful`/`.paper-blank` from `#section-data`; "N fields to check" in the entry bar
- [x] 9.5 `entry_saved` for a sheet session: `sheet.status='entered'`, `entered_at`, `delete_sheet_images.delay`, `paper_sheet_entered` with `fields_total`/`fields_doubtful`/`fields_changed` (diff prefill vs stored answers by code); *Next sheet* → next `review`/`incomplete` sheet of the batch (POST enter) or the batch page
- [x] 9.6 `sheet_skip`: `skipped`, images deleted, empty session trashed
- [x] 9.7 Tests in `test_paper_photo_entry.py` + `test_operator_entry.py`: review creates the session from the form (version, language, source, link) with no `Answer`; prefilled radio and text in the HTML; saved rows win; doubtful listed and counted; pane shows the section's page; typed-in session renders no pane/prefill; entered → sheet state, images gone, event counts; next sheet; skip
- [x] 9.8 Page-by-page review (owner, first live check 2026-10-31): `sheet_page(n)` + `_page_plan` over `layout[n]["items"]`, shell section + extra forms in one `<form>`, `_build_section_context(questions_filter=)`, `save_section_answers(only_questions=)`, "Page n of N" and Back/Next/Finish in page mode, old forms fall back to the section flow
- [x] 9.9 Missing page attached from the review: attach box in the pane (Take photo / choose files), `PaperUpload.sheet` + `expected_page`, pinned pages, manual code for an unreadable QR, `…/pages/<n>/status/` + reload; photo on the LEFT, form on the right; the camera button on the batch page
- [x] 9.10 Tests: page 1 renders only its questions; a section spanning two pages keeps both pages' answers; a missing page attached and read; old form falls back

## 10. Lifetime, events, drawer, export

- [x] 10.1 `survey/management/commands/sweep_paper_batches.py` (dry run default, `--delete`): close batches past `PAPER_BATCH_TTL_DAYS`, delete remaining images and uploads; `render.yaml` cron `mapsurvey-paper-sweep` daily, previews off
- [x] 10.2 `product_events.py`: `PAPER_BATCH_CREATED`, `PAPER_PAGE_RECOGNISED`, `PAPER_SHEET_ENTERED`; emitted with the listed properties only; tests assert the property sets
- [x] 10.3 Detail drawer: "Sheet N of batch M" with the batch link; `export.py` `sessions` table + ZIP file: `paper_batch`, `paper_sheet`; tests in `test_responses_detail_drawer.py` / `test_responses_export_formats.py`
- [x] 10.4 `/trust/`: retention sentence for uploaded sheet images and the provider disclosure; `TERMS_UPDATED` untouched (trust page, not terms)

## 11. Help, strings, changelog, hygiene

- [x] 11.1 Help page `help/src/content/docs/how-to/enter-paper-forms-from-photos.md` (how to photograph: whole page, flat, all four corner marks in frame; what the model reads well and badly; the review); `help_links` key `paper_photos`; "Learn more" link on the batch page; `npm run build` in `help/` passes
- [x] 11.2 New creator strings appended to every offered catalog by hand (`TranslationCatalogHygieneTest`); `compilemessages`
- [x] 11.3 Changelog entry — taken out of this PR (owner 2026-11-06: no What's new card for now); moved to #536
- [x] 11.4 `POSTHOG_EXCLUDED_VIEW_NAMES` unchanged (batch pages are creator surfaces and ARE tracked); `_posthog_scrub_tags` needs nothing (no respondent prefix)
- [x] 11.5 CLAUDE.md paragraph "Paper photos (change paper-photo-entry, #495)" next to the operator-entry/printable-form notes: the four rows, the worker-only rule, the items map, the prefill seam, the image lifetime

## 13. v2 — numbered copies, placement by the code, Paper responses (owner, 2026-10-31)

The first live check split one form into two responses (grouping by upload order). Journey and
decisions agreed on `journey.mockup.html`; owner rules: unique copies sort a shuffled stack, the page
number is read without AI, one form starts as an empty response.

- [x] 13.1 `PrintRun` (MAX_COPIES 200): numbers per canonical survey, only grow, handed out under `select_for_update` on the canonical header; `PaperUpload.sheet/expected_page/is_pdf`, `PaperPage.copy` + status `replaced` + `code_source` `qr|manual`, `PaperSheet.copy/source_upload/created_by/last_activity_at/label`, constraint `paper_sheet_one_per_copy`; `SurveySession.paper_sheet` OneToOne; `paper_code` kind dropped; migration `0113` regenerated (renumbered `0115` on the rebase onto master, 2026-11-06)
- [x] 13.2 `form_code`: `Code(form_id, copy, page, pages)`, payload `MSFORM:<form>:<copy>:<page>:<pages>`, old payload still parses; `pdf.py`: two vector QR 20 mm level H in the bottom corners, footer line `MS-<form> · #<copy> · Page n of N`, `#copy` top right, `LAYOUT_VERSION = 2` in the structure hash
- [x] 13.3 `_CopiesCanvas`: body pages as Form XObjects, every copy = `doForm` + chrome + codes; `build_form(copies=)`, `print_copies`; `?mode=copies&copies=N|single`, 400 on bad values, filename with the range, `form_printed.copies`; Share dialog radios + counter + photocopy note
- [x] 13.4 `paper/codes.py` local only (full image ≤ 1800 px, then 2× bottom corners); ingest decodes at full resolution before shrinking, PDF at 200 dpi; the model fallback removed
- [x] 13.5 `paper/sheets.py` rewritten: `inbox_for`, `new_sheet`, `place_page` (copy → its response; dropped into → there; one PDF → one response; loose unnumbered photo → set aside; stored / other form → set aside; duplicate page → `replaced`), `restore_page`, `assign_page`, `remove_page`, `missing_pages`, `refresh_sheet`, `next_reviewable` (complete first)
- [x] 13.6 `recognise_paper_page`: place by code, re-decode the stored JPEG, manual page number from `expected_page`, `check_quota(org, 'paper_page')` before the call, extraction, a page `replaced` mid-read keeps no result; accounting trace `paper-response-<id>`
- [x] 13.7 Views and URLs: `paper_home` (+ `list/`), `new/`, `next/`, `upload/`, `r/<id>/` (+ `slots/`, `check/`, `skip/`, `pages/<n>/`, `pages/<n>/status/`), `pages/<id>/image|remove|restore|assign|retry/`; stepper `goto` on the page check; templates `editor/paper/home.html`, `_home_list.html`, `response.html`, `_response_slots.html`; `css/paper_inbox.css`, `js/paper_upload.js` (sequential uploads, `data-sheet`, camera); batch templates and `paper_batch.*` removed
- [x] 13.8 Saved page "<label> stored" + *Check next*; entry bar, drawer and Responses link use the label; export column `paper_copy` replaces `paper_batch`/`paper_sheet`; event `paper_response_created` replaces `paper_batch_created`; sweep skips stale open responses and deletes set-aside images and originals
- [x] 13.9 Strings: v2 strings in all ten catalogs; only this change's own obsolete v1 entries dropped; compiled; i18n hygiene green
- [x] 13.10 Tests rewritten in `test_paper_photo_entry.py` (gate, upload, ingest, placement scenarios, extraction + quota, page check, missing page, sweep, events) and `test_printable_form.py` (footer, copies numbering, bounds)
- [x] 13.11 OpenSpec artefacts: proposal, design (D1, D3, D4, D7, D8, D10), `paper-photo-entry` spec rewritten, `printable-form` delta (two QR, copies), `operator-entry` delta (Check next, `paper_copy`)
- [x] 13.12 Help page `how-to/enter-paper-forms-from-photos` and the printing page rewritten for copies / New response / Upload a stack; CLAUDE.md paragraph updated
- [x] 13.13 Full suite `./run_tests.sh survey billing api mcp newsletter`; `openspec validate paper-photo-entry --strict`
- [x] 13.14 Second live check (2026-10-31): page 1 of a single-QR form with the footer cropped is placed by the page-1 online-link QR (`codes.shows_first_page_link`); a code-less photo dropped into a response offers "It is page [n]" + Attach; Check button back to normal size; Responses toolbar buttons one height
- [x] 13.15 × on every notice of a response page (`paper_page_dismiss`): deletes a replaced or set-aside photo, clears the note of one that went to its own copy
- [x] 13.16 Photo and form scroll independently on the page check: `#paper-stage` is `position: fixed` (an absolute stage scrolled away with a tall form page); the photo keeps its own scroll, Ctrl+wheel zooms
- [x] 13.17 Dates: the prompt asks for YYYY-MM-DD[THH:MM] read day-first; `extract.normalise_datetime` turns the answer into the datetime-local value (a date without a time gets 00:00 and is doubtful; an unparseable one is null and doubtful) — the browser drops any other shape silently
- [x] 13.18 One header over photo and form on desktop (`paper_review.js::buildHead`): ← Paper responses · label · form · fields to check | page stepper | zoom, rotate, Map, Stop; the entry bar and pane bar are hidden; a paper check renders `data-panel-side="right"` so the photo stays left on map sections
- [x] 13.19 The form leads, the photo follows: the extraction asks for a `box` per field (`extract._box`, `page_boxes`); the pane gets each photo's boxes (`review.pane_pages_json`); `paper_review.js::makeFollow` scrolls the photo to the active question's box and outlines it (proportional scroll without a box or when rotated)
- [x] 13.20 New response button is `btn-sm` like every primary action in the editor

## 14. Marks on the printed map → coordinates (epic #350 item 4, same PR; owner 2026-10-31)

- [x] 14.1 `structure.mark_letters` shared by `pdf.py` and the reader; `prompts.py`: the marks rules, `marks` + `map_frame` in the schema, `USER_MAP_HEAD`; `extract.geo_items_for_page`, `build_user_message(geo_items)`, `extract_page` places the marks on the photo it still holds
- [x] 14.2 `survey/paper/marks.py`: `find_alignment_squares` (pure Pillow), `homography`/`apply`, `photo_to_page` (squares, else the model's frame box), `mm_to_lnglat` (Mercator through the frame record), `geometry_for` (point / line / polygon / spray cloud), `place_marks` → `{code: {value: features, marks, placement, box}}`
- [x] 14.3 Prefill: `sheet_prefill` passes features for geo questions, `_build_section_context` routes them into `existing_geo_answers` (never `initial`); `changed_fields` counts features; `_page_plan` gives a section's geo questions to the page with its frame and to no other
- [x] 14.4 Tests (`MarksTest`): squares on a straight render and on a perspective-warped "phone shot" over a dark table (≤ 2 mm), Mercator placement of centre/corner/outside, extraction end to end with the row answers, frame-box fallback and the raw-marks case, geometry shapes, the check's map prefilled
- [x] 14.5 Live check on dev with the real model (a drawn dot + "A1" on a rendered map page); help page and CLAUDE.md paragraph; `openspec validate --strict`; full suite
- [x] 14.6 The map page reads like the paper (owner, `map-page.mockup.html`): `paper_map_mode` → form layout half and half, `_paper_marks.html` + `js/paper_marks.js` (frame map, marks table with the printed rows and columns, Show / remove / place / add, hidden inputs in the POST dialect), `_paper_map_context`, `views.geo_answer_features` shared; printed choice columns get boxes in every row (`pdf._sub_cell`); tests, strings in ten catalogs
- [x] 14.7 Blocks of a page in the paper's order: `_page_plan` sorts sections by where their heading or first question is drawn, `paper_blocks` renders them in that order with the marks block where the frame section starts (the frame section used to come first as the shell)
- [x] 14.8 Registration after the second live check (owner 2026-11-01): fiducial squares beside the frame (`FIDUCIAL_SIZE`/`FIDUCIAL_OFFSET`, `fiducials`/`fiducial_dx_mm` in the frame record, `LAYOUT_VERSION = 3`), `find_frame_fiducials` preferred over page squares; threshold ladder in `_square_in`; page squares must form a portrait quadrilateral; prompt: the symbol's ink, not the label; test on a photo cropped to the map at an angle
- [x] 14.9 Page squares at full resolution with a solid-through check (a QR finder centre passed for a cut-off square); `map_frame_corners` from the model as the fallback for forms without fiducials, `_frame_quad` → homography; page 7 re-placed within a few hundred metres
- [x] 14.10 Upload UX (owner 2026-11-01, ten pages in a row): `place_new_page` at ingest, reads queued by `read_pending_pages` after `READ_SETTLE_SECONDS` without new uploads (`schedule_reading` armed once per inbox via a cache key), in response and page order; one collapsible Notes block with `paper_response_dismiss_notes`; file questions left off the paper
- [x] 14.11 Registration = one weighted least-squares fit over every landmark (`fit_homography`: fiducials ×4, page squares ×1; `find_frame_fiducials` returns what it found, None per missing corner): copy 165 page 2 on a bent page went from 10 mm off to on the ink with three fiducials + four squares; file questions left off the paper (`plan_items`)
- [x] 14.13 Delete replaces Skip (owner 2026-11-01): `sheets.delete_sheet` removes an open response whole and frees its copy number; the sweep deletes stale open responses the same way; status `skipped` gone
- [x] 14.14 Fiducial weight 50 (vs squares 1) when ≥ 3 are found: on a bent page the 4:1 compromise still put a dot 3 mm off; residuals at the fiducials now ≤ 0.4 mm
- [x] 14.15 Bent paper (owner 2026-11-01): mid-side fiducials (`fiducial_mids`, `LAYOUT_VERSION = 4`, `fiducial_targets`) and the thin-plate-spline residual correction in `fit_registration` (`apply` takes the `{h, tps}` registration); test with a simulated bend: plane off by millimetres, corrected within 1 mm
- [x] 14.16 Re-shot page (owner 2026-11-01): `review.supersede_machine_answers` drops stored rows that equal the earlier reading, keeps the operator's edits; the table shot of copy 165 now shows on the map (A2 on the dispensary)
- [x] 14.12 Print dialog: "Keep each map with its tables on one page" (`?keep=1`, default on; `build_form(keep=)` wraps heading + frame + legend + tables in one KeepTogether; `keep` in the structure hash; `form_printed.keep_together`) — the A2/A3 rows on the next page read as a cut question
- [x] 14.17 Frame edges and corners as landmarks (`find_frame_edges`, `frame_corners_from_edges`; EDGE ×10, CORNER ×30): the border sampled all around pins the bend where fiducials are missing; `TPS_SMOOTHING = 0.1` (1e-4 overfit edge noise to 11 mm); page squares never feed the spline (`bend=False`)
- [x] 14.18 The printed map as the reference (`survey/paper/texture.py`): on the lap shot of copy 165 the border registered to 0.3 mm and A2 was still 5.5 mm off — the page bows INSIDE the frame. The frame image is kept at print time (`paper_refs/<form>-<page>.png` on the private tier, `ref_key` in the frame record; older forms re-render it), the photo is rectified through the current registration, reference patches are matched by FFT normalised cross-correlation at a 6×4 grid of anchors, the matches join the fit as landmarks (×20) and the spline follows them; up to three rounds (match → refit → rectify again) reach a bend the first window clipped. Edge samples are re-anchored ALONG their side on every refit (`_fit_with_edges`) — across the side they pin the paper, along it they only repeated the first plane. A2: 5.5 mm → 0.4 mm; 2.5 s a page
- [x] 14.19 Test: a textured map with a 4-mm bow inside the frame only — the border alone misses the middle by > 2 mm, with the reference every probe is within 1 mm; the reference is kept on print with a basemap and not with the grid
- [x] 14.20 The dot's ink, not the model's vertex (owner 2026-11-01, copy 166: A1 reported at the label, 4.3 mm from the dot while the map was aligned to 0.2 mm): `texture.snap_to_ink` — rectified photo minus reference within 7 mm of the model's point, compact blobs 0.8–4.5 mm with discness ≥ 0.5 (area over the circle around the box; a serifed "1" is 0.3, an A 0.4), the nearest one wins; `place_marks` applies it to `point` questions only (`_snap_point`, `snapped` count on the field), lines and polygons wait for ink tracing
- [x] 14.21 The hybrid (owner 2026-11-01: "AI is not needed for the map — an analytical module"): `survey/paper/ink.py` reads the marks off the registered photo — ink = coloured against the 8-mm paper around it (a blue pen; darker than the darkest print within 3 px, on light print) ∪ darker than the paper's 8-mm mean by 50, its 3-mm mean by 30 and the darkest print by 40 (a black pen), never on near-black print; HSV saturation, absolute chroma and darkness alone each failed on one of the two photographed copies; components → hatched cluster (spray), closed loop (area), stroke with two ends (line, pieces sewn across the pen's skips, an outline whose ends meet closed), filled disc (point), glyph-sized rest (writing). `place_marks` pairs the model's marks with the ink by the median distance of their vertices (`_match_marks`; a line's further pieces along one mark are sewn to it), takes the geometry from the ink and the label/row answers from the model; ink the model did not name becomes a numbered mark at confidence 0.5 (doubtful) when the kind has one question on the page; a model mark the ink does not show falls back to its vertices at 0.6; the model's new `label_box` excludes ink under the handwritten label. Copy 165: routes A1–A3, the C circle, the D hatching, the B line all from ink. OPEN: a false piece or two per page still comes through (a shadow's edge, an outline left as a line) at confidence 0.5 — flagged for the operator, not yet gone
- [x] 14.22 Copy 164 page 2 (owner's photo, 2026-11-01, "you found the points right"): a fine pen's 1.2-mm dot is a WEAK point (`DOT_WEAK_MIN_MM`, admitted by a model mark within 8 mm); a dot drawn on printed text is found by a second pass without the print test (`ink.unprinted_dots`, weak, 3-mm penalty against dots the print test admitted — POI icons are such dots too); a line along a frame side within 8 mm is the border off its registration on a curled page and is dropped (`_along_frame_edge`). All three dots from the ink; standalone check page `points_164_p2.html`
- [x] 14.23 A marks table that runs onto the next page (Stack #263; copy 165 of MS-6, before keep-together — and a long table splits with it): `extract.table_items_for_page` names the geo questions whose table continues on a page (from the frame's page to the page of the question's own `question:<code>` marker, which follows the table on paper), the model is asked for those rows as marks without points (`USER_TABLE_HEAD`), `marks.table_rows` stores them as a `rows_only` field, `merge_pages` attaches them to the map page's field as `rows_extra`, and `_paper_map_context` gives each row's answers to the placed mark of the same label or lists it as `unplaced` — the check's table shows the row filled, with a *place it on the map* link
- [x] 14.24 A page thumbnail on the response card opens the check at that page (owner 2026-11-06): each slot is a `Check page N` button posting `page=N` to `paper_response_check`, which creates the session as before and redirects to `paper_response_page` N (out of range → 1); test `test_a_page_thumbnail_opens_the_check_at_that_page`
- [x] 14.25 Two basemaps made for print (owner 2026-11-06, ahead of #534): `paper` = Paper A (Mapsurvey Print A — white ground, cased streets with names, no POI icons or shields, city names only at zoom ≤ 10, no footpaths) and `paper_b` = Paper B (the planner's map after a customer's printed neighbourhood map — white streets, bold names, light-green parks, teal water); Mapbox styles in the owner's account, `MAPBOX_PAPER_STYLE` / `MAPBOX_PAPER_B_STYLE`, offered wherever basemaps are chosen and used by the printed frame; choices-only migration `0116_paper_basemaps`
- [x] 14.26 Settings page: the "Made with Mapsurvey" switch rendered twice (the generic field loop and its own block), the loop's bare `position:absolute` copy floating over the field above; the loop skips it (bug on master too)

## 12. Verification

- [x] 12.1 `./run_tests.sh survey.tests.test_paper_photo_entry survey.tests.test_operator_entry survey.tests.test_printable_form survey.tests.test_ai_survey_generation survey.tests.test_test_suite`, then the full `survey billing api mcp newsletter` once
- [x] 12.2 Live check on the worktree dev stack (done by the owner, 2026-10-31…11-06, copies 164–167) (`/verify`): print a two-page form of a seeded survey, photograph it with a phone (and export one HEIC), upload the photos plus the PDF, watch the list, print numbered copies, upload a shuffled stack, check one response end to end, confirm the session on Responses with the copy link, confirm the images are gone after entering
- [x] 12.3 Moved to #536 (not measured before the merge) — Memory bump: `GUNICORN`/worker RSS before and after ingesting a 50-page PDF on the dev stack (the web process must not move)
