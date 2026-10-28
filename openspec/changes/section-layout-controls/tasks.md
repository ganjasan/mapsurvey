## 1. Model and one definition of map-less stages

- [x] 1.1 `survey/models.py`: `SECTION_LAYOUT_CHOICES` += `image`; `PANEL_SIDE_CHOICES`, `PANEL_WIDTH_CHOICES`; `MAPLESS_LAYOUTS = ('form', 'image')`; fields `panel_side`, `panel_width`, `stage_image` (`upload_to='sections/'`) with help texts
- [x] 1.2 Migration `0106_section_layout_controls`
- [x] 1.3 Replace every `== 'form'` geo-exclusion test with `in MAPLESS_LAYOUTS`: `SurveySectionForm.clean_layout`, the geo check in `QuestionForm`, the type-picker filtering in the editor, `serialization` import whitelist
- [x] 1.4 Purge path: delete `stage_image` files with covers and question images

## 2. Respondent page

- [x] 2.1 `partials/survey_section_partial.html`: `data-panel-side`, `data-panel-width`, `data-stage-image` (section picture → survey cover → empty) on `#section-data`
- [x] 2.2 `base_survey_template.html`: server-side body classes for stage/side/width; `<div id="stage-image">` beside `#map` with the inline background for a direct load; HTMX step 0 → `applyLayout(dataset)` toggling the classes and the picture, `invalidateSize` only for `map`; geolocation guard on `layout !== 'map'`
- [x] 2.3 `main.css`: `--panel-w` variable (420 px default, `panel-w-third`, `panel-w-half`), `#info_page` and `.leaflet-top.leaflet-left` on the variable with the default unchanged; `survey-image-layout` sharing the no-map-chrome block with `survey-form-layout`, plus `#showButton`/`#closeButton` hidden; `#stage-image` rules and the tinted fallback; `body.panel-right` mirror block (panel, hidden transform, show/close buttons and chevrons, Leaflet corners, and every other rule found by grepping `436px` / panel offsets)
- [x] 2.4 Mobile block: re-assert the left overlay regardless of side/width classes; `survey-image-layout` → picture band (38vh) + relative full-width panel in one scrolling column
- [x] 2.5 Manual pass at desktop and 390 px: 3 stages × 2 sides × 3 widths on a test survey, including hide/show panel, draw bar, search box, basemap switcher and the embed snippet

## 3. Editor

- [x] 3.1 `SurveySectionForm`: fields, widgets (`ClearableFileInput`), labels, help texts; `services.sections.update(..., files=None)` → `bind(..., files)`; `editor_section_detail` passes `request.FILES`
- [x] 3.2 `section_detail_form.html`: multipart (`enctype` + `hx-encoding`), a "Layout" fieldset with stage / side / width / picture (current picture thumbnail + clear), `syncLayoutControls()` on `#id_section_layout` change (side+width for map|image, picture for image, Map position for map)
- [x] 3.3 New creator strings appended to every offered catalog (`TranslationCatalogHygieneTest`)

## 4. Copies, ZIP, API and MCP

- [x] 4.1 `cloning.copy_section`: copy the `stage_image` file across families like `Question.image`; `DraftCopyKeepsFieldsTest` / `DuplicateSurveyKeepsFieldsTest` green
- [x] 4.2 `serialization`: export the three values + `images/sections/<code>_<name>`; import with whitelist + default fallback; extract pictures by section code with warnings on mismatch
- [x] 4.3 `api/v1/schemas.py` (`SectionIn` literals, `SectionOut` + `stage_image` URL), `forms_bridge.SECTION_FIELDS`, `api/v1/out.py`
- [x] 4.4 `mcp/tools/sections.py` descriptions; regenerate `reference/api.md` and `reference/mcp-tools.md`

## 5. Tests (`survey/tests/test_section_form_layout.py`, `api/tests`, `mcp/tests`)

- [x] 5.1 Rendering: body classes and `#stage-image` for each stage/side/width; defaults byte-identical for a `map` section; picture source order (section → cover → tinted, no empty `<img>`); unknown `panel_width` renders as default; `form` ignores side/width
- [x] 5.2 Geo exclusion for `image` (question save, layout switch, type picker) through `MAPLESS_LAYOUTS`
- [x] 5.3 Live survey: side/width/stage change saves in place, no draft; draft copy keeps the four values and the picture
- [x] 5.4 ZIP round trip with picture; legacy archive defaults; unknown value → default
- [x] 5.5 Editor modal: multipart upload of a picture through `editor_section_detail`, clear picture
- [x] 5.6 API: PATCH with the three fields, `422` on `panel_width: "wide"`, `SectionOut` carries them; MCP `update_section` accepts them
- [x] 5.7 `./run_tests.sh survey api mcp` green

## 6. Help, changelog, docs

- [x] 6.1 Help centre how-to "Lay out a section: map, picture or form; panel side and width" (with the welcome-page recipe), linked from the Layout block via `help_links` if a "Learn more" is added
- [x] 6.2 `survey/changelog/2026-10-XX-section-layout.html` (`kind: new`)
- [x] 6.3 `CLAUDE.md`: a paragraph on section layout controls (one constant for map-less stages, body classes + `--panel-w`, mobile rule)
