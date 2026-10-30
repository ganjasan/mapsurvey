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

- [x] 5.1 `survey/paper/ingest.py`: sniff type from bytes; PDF via `pypdfium2` page by page at 150 dpi; images via Pillow (+`pillow-heif`), EXIF transpose; normalise to JPEG ≤ 2200 px q85; `PaperPage` rows with consecutive `seq`; delete the original; `PaperUpload` status + `pages_count`; failures recorded with a plain message
- [x] 5.2 `survey/paper/codes.py::read_code(image_bytes)`: `zxing-cpp` over the page and over 2× corner crops; parse with `form_code.parse`; return `(form_id, page, pages, source)` or None
- [x] 5.3 Fallback `read_code_with_model(image_bytes)`: tiny vision call (schema `{code}`), `form_code.parse` tolerance; `code_source='text'`
- [x] 5.4 Tasks in `survey/tasks.py`: `ingest_paper_upload(upload_id)` (idempotent: a row past `queued` returns), `recognise_paper_page(page_id)` (code → placement → extraction; transient provider errors retried twice with backoff), `delete_sheet_images(sheet_id)`
- [x] 5.5 Tests (`survey/tests/test_paper_photo_entry.py`, eager tasks like `_eager_import`): a PDF printed by `build_form` and rendered through `pypdfium2` round-trips its QR on every page; an EXIF-rotated JPEG is upright; HEIC converts; `.docx` fails cleanly; a 6000 px image is bounded

## 6. Placement into sheets

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

## 10. Lifetime, events, drawer, export

- [x] 10.1 `survey/management/commands/sweep_paper_batches.py` (dry run default, `--delete`): close batches past `PAPER_BATCH_TTL_DAYS`, delete remaining images and uploads; `render.yaml` cron `mapsurvey-paper-sweep` daily, previews off
- [x] 10.2 `product_events.py`: `PAPER_BATCH_CREATED`, `PAPER_PAGE_RECOGNISED`, `PAPER_SHEET_ENTERED`; emitted with the listed properties only; tests assert the property sets
- [x] 10.3 Detail drawer: "Sheet N of batch M" with the batch link; `export.py` `sessions` table + ZIP file: `paper_batch`, `paper_sheet`; tests in `test_responses_detail_drawer.py` / `test_responses_export_formats.py`
- [x] 10.4 `/trust/`: retention sentence for uploaded sheet images and the provider disclosure; `TERMS_UPDATED` untouched (trust page, not terms)

## 11. Help, strings, changelog, hygiene

- [x] 11.1 Help page `help/src/content/docs/how-to/enter-paper-forms-from-photos.md` (how to photograph: whole page, flat, all four corner marks in frame; what the model reads well and badly; the review); `help_links` key `paper_photos`; "Learn more" link on the batch page; `npm run build` in `help/` passes
- [x] 11.2 New creator strings appended to every offered catalog by hand (`TranslationCatalogHygieneTest`); `compilemessages`
- [x] 11.3 Changelog entry `survey/changelog/<date>-paper-photos.html` (kind `new`, amends the paper-responses story of items 1–2 if a card exists for the epic — one card per epic)
- [x] 11.4 `POSTHOG_EXCLUDED_VIEW_NAMES` unchanged (batch pages are creator surfaces and ARE tracked); `_posthog_scrub_tags` needs nothing (no respondent prefix)
- [x] 11.5 CLAUDE.md paragraph "Paper photos (change paper-photo-entry, #495)" next to the operator-entry/printable-form notes: the four rows, the worker-only rule, the items map, the prefill seam, the image lifetime

## 12. Verification

- [x] 12.1 `./run_tests.sh survey.tests.test_paper_photo_entry survey.tests.test_operator_entry survey.tests.test_printable_form survey.tests.test_ai_survey_generation survey.tests.test_test_suite`, then the full `survey billing api mcp newsletter` once
- [ ] 12.2 Live check on the worktree dev stack (`/verify`): print a two-page form of a seeded survey, photograph it with a phone (and export one HEIC), upload the photos plus the PDF, watch the list, review one sheet end to end, confirm the session on Responses with the sheet link, confirm the images are gone after entering
- [ ] 12.3 Memory bump: `GUNICORN`/worker RSS before and after ingesting a 50-page PDF on the dev stack (the web process must not move)
