## 1. Dependencies, fonts, model

- [x] 1.1 Pipfile: `reportlab = "~=4.4"`; dev `pypdf = "*"`; install both into the shared venv (`uv pip install --python env/bin/python reportlab pypdf`), note in CLAUDE.md's venv paragraph
- [x] 1.2 `survey/print/fonts/`: DejaVuSans.ttf, DejaVuSans-Bold.ttf + LICENSE (Bitstream Vera); `survey/print/__init__.py` registers them with reportlab once per process
- [x] 1.3 `PrintedForm` model (survey FK canonical, `version_number`, `language`, `paper`, `structure_hash`, `pages`, `layout` JSON, `tracked_link` FK SET_NULL, `created_by` SET_NULL, `created_at`; unique on (survey, version_number, language, paper, structure_hash)); `code` property (base32 id); migration `0112_printedform` (check `origin/master` for a parallel 0110 first)

## 2. Form code, static map

- [x] 2.1 `survey/print/form_code.py`: `encode(form_id)`/`decode(text)`, `qr_payload(form, page, pages)`, `qr_png(payload, mm)` via `segno` → Pillow image
- [x] 2.2 `survey/print/static_map.py`: `resolve_frame(section, survey)` → (centre, zoom, basemap) with the fallback chain (section → survey → layer bounds → world); `basemap_style(name)`; `fetch_basemap(style, centre, zoom, size)` (Static Images `@2x`, `attribution=false&logo=false`, 5 s timeout, cache 24 h, returns None on any failure); `draw_layers(image, survey, centre, zoom)` (Web Mercator projection, `layers_for(survey).defer(None)`, `normalize_style` + `match_class`, labels, 20 000-feature cap); `draw_grid(image)` for the unavailable case; `scale_bar(zoom, lat)`; `bounds_of(centre, zoom, size)` → `[w, s, e, n]`
- [x] 2.3 Tests `survey/tests/test_printable_form.py` — static map part: fallback chain, style mapping, token empty → None + grid, timeout → None, cache hit on second call (requests mocked), a polygon and a point layer drawn (pixel asserted), bounds round-trip

## 3. The PDF

- [x] 3.1 `survey/print/pdf.py`: `FormDocument` (A4/Letter, margins, page template with the four marks, header survey/section, footer code + page N of M + QR, DRAFT watermark); `build_form(survey, language, paper, *, user)` → (`bytes`, `PrintedForm`), structure walk with `compute_visibility(surface='respondent')` + `group_runs`, "Answer only if" from `describe_rule`, `structure_hash`
- [x] 3.2 `QUESTION_SHAPES` — one factory per type: text, text_line, number, choice, multichoice (write-in line for `other`), range, rating, thumbs, datetime, ranking, html, image, photo/audio/document (Online only), default for unknown; required asterisk; help text
- [x] 3.3 Map page parts: `MapFrame` flowable (reports its drawn rectangle into the layout), legend rows (letter, symbol, name, allowed count, colour swatch), sub-question table (A1…An), Objects-on-the-map table (≤60 rows), attribution line; page-1 online QR via `TrackedLink` get-or-create (`paper`/`print_form`) and the Office-use box
- [x] 3.4 Fixed strings through `gettext` under `translation.override(language)`; add them to every respondent catalog (75) by hand; extend `test_every_respondent_string_is_translated_in_every_catalog` to walk a printed form
- [x] 3.5 Tests — PDF part (`pypdf` text/page count): order and translations, operator-only absent, condition line, unknown type fails open, choice write-in, file question note, map frame + legend + sub-question table + objects table, form-layout section has no frame, marks and footer on every page (QR payload decoded with `segno`? — assert the payload string we encoded), tracked link reused, `PrintedForm` reuse / new row after structural change / layout records the frame, watermark on draft only

## 4. View, Share page, event, help

- [x] 4.1 `survey/print/views.py::print_form` (`survey_permission_required('editor')`, `lang` ∈ `available_languages`, `paper` ∈ {a4, letter}, else 400; `FileResponse` attachment `<survey>-form-<lang>-<paper>.pdf`; `pe.emit(FORM_PRINTED, …)`); URL `editor/surveys/<uuid>/print/form/` name `editor_survey_print_form`; `FORM_PRINTED` in `product_events.py`
- [x] 4.2 Share page: `share_views._render_share` passes languages + default paper (locale rule); `survey_share.html` section "Print a paper form" above Embed, rendered for every status; dialog strings in the 10 creator catalogs
- [x] 4.3 Help page `how-to/print-a-paper-form.md` (what prints, the map and letters, the code, "then enter the sheets" → entry form page), `help_links` key `print_form`, link from the section and from `enter-responses-for-others.md`
- [x] 4.4 Tests: view roles/400s/attachment/event (`test_printable_form.py`), Share page section in draft and published, language select rule, Letter preselect (`test_share_page.py` delta), event payload (`test_creator_distribution_events.py` delta)

## 5. Verification

- [x] 5.1 `SpecTestLineageTest`: `printable-form` in `UNMAPPED_MODULES` until archive ("spec lives in the unarchived change printable-form")
- [x] 5.2 Full run `./run_tests.sh survey billing api mcp newsletter`; `openspec validate printable-form --strict`
- [x] 5.3 `/verify`: print the Park survey (point question, reference layer, group, conditional question, operator-only section) in two languages and both papers with a real Mapbox token; open the PDFs; photocopy-style check: print one page to B&W PDF and confirm boxes, marks and legend symbols stay legible
- [x] 5.4 `.env.example`: note beside `MAPBOX_ACCESS_TOKEN` that the printable form uses the Static Images API (a separate, metered Mapbox SKU, cached a day per frame); `billing/README.md` has no cost list to extend
