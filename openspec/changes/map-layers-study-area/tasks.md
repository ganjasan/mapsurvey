## 0. Prerequisites

- [x] 0.1 Archive `layers-by-question` (its code shipped): move its open tasks 1.4 (`hidden_layers` drop) and 4.1 (upload from the question form) into this change, sync its deltas into the main specs, check that every MODIFIED/REMOVED header of this change now exists in `openspec/specs/` (archive trap)
- [x] 0.2 Owner answers to design open questions 1–3 (2026-11-24: line → buffered corridor, point → rectangle; no map in form sections, placed layers start on; study area outline on Responses and Reports in this change)
- [x] 0.3 Help-centre outline: rewrite of the reference-layers guide + a new study-area page (registry keys in `survey/help_links.py`)

## 1. Models and migrations (PR 1)

- [x] 1.1 `LayerPlacement` (canonical survey, layer, scope, section refs, position; unique survey+layer) and `StudyArea` (one-to-one canonical survey, MultiPolygon 4326, source, place_name, osm_ref, fog, refuse_outside, message, refused_marks)
- [x] 1.2 Data migration A: top-level `layer_objects` questions of canonical map sections → placements (scope `all` when every map section is covered; order = layer position, the old stacking order; draft-copy questions included); idempotent
- [x] 1.3 Data migration B: `upload` layers move to the workspace (`survey=NULL`, `organization`), `public` Data row, one `DatasetLink` per canonical survey, in one transaction; `question` layers untouched
- [x] 1.4 Migration tests on historical models (GIVEN/WHEN/THEN): legend on every section → one `all` placement; asking question keeps working; layers reachable through links

## 2. Placement core

- [x] 2.1 `survey/services/placements.py`: place, unplace, set_scope, reorder; strict validation (layer must be linked, section refs must exist); audit rows; `Actor`
- [x] 2.2 `section_layer_ids` reads placements only (section ref `<code>#<n>` resolver shared with the translation table); `build_map_layers_metadata` carries per-section visible ids
- [x] 2.3 Objects question save places its layer (same service call); `panel_mode` no longer read; legend-only questions hidden in the editor and rendered as nothing for respondents
- [x] 2.4 Shared-map layer lifetime: reader = placement or Objects question in any header
- [x] 2.5 Tests in `survey/tests/test_map_layer_placement.py` (new module, add to the spec↔module lineage): scope `all` incl. a section added later and skipping form sections, layer from Survey settings on every map section and switched on, picked sections, repeated codes, draft copy reads canonical, live survey edit in place, viewer refused

## 3. Layers live in Data

- [x] 3.1 Survey upload read synchronously up to the survey cap (WGS 84 GeoJSON by the survey parser, projected GeoJSON and GPKG/SHP/KML/CSV by the Data reader, reprojected), creates workspace layer + `public` row + link + placement
- [x] 3.2 `layers_for` = links + own `question` layers; layer editor/style endpoints address the layer through its dataset; guards (`data/links.py`) refuse placing an unlinked layer and unlinking one that is asked about
- [x] 3.3 Settings card → "Layers used here" (where shown with scope control, Open in Data, Remove from this survey, + Layer placing with scope `all`); survey delete dialog says layers stay in Data
- [x] 3.4 Tests in the modified modules (`test_reference_overlay_layers.py`, `test_data_links.py`, `test_data_upload.py`): State Plane GeoJSON reprojected, upload is a dataset with "Used by", delete keeps datasets

## 4. Build UI: the Map card

- [x] 4.1 Map card partial at the top of map-section panels (study area row, placed layers with use and scope, + Layer menu: Upload / From Data / Draw), autosaved toggles, `data-gate`-free (content edit)
- [x] 4.2 Add layer dialog (reuse the editor's modal): file recognised, reprojection note, name, "looks like a boundary → make it the study area / keep as layer", scope radio; no `confirm()`
- [x] 4.3 Objects question form: layer picker marks layers not on this section, *Upload a new layer*, hint when no sub-questions, List/Legend control removed
- [x] 4.4 Section settings: remove any layer list; help text names the Map card
- [x] 4.5 Respondent + preview: "On this map" legend block from placements, toggles wired to the layers control, every placed layer switched on at section load

## 5. Study area

- [x] 5.1 `survey/services/study_area.py`: set/update/clear, geometry validation (`ST_MakeValid`, polygonal, bounds), simplification to ≤2,000 vertices, audit
- [x] 5.2 Boundary lookup endpoint (Nominatim `polygon_geojson`, project User-Agent, 30-day cache, `limits.hit(user, 'study_area_lookup')`, failure message); up to 5 candidates; line results → corridor (`ST_Buffer` geography, 50/100/200 m, rebuilt on width change from the cache); point results → rectangle (bbox > 100 m, else 500 × 500 m)
- [x] 5.3 Study area editor page (place search, candidates, corridor width control, Leaflet.draw vertex editing, upload / layer / draw secondary paths, fog and refusal settings, message, OSM credit)
- [x] 5.4 Respondent map: open on the area (keep a section start inside it), fog pane, outline; map-start chain gets a `study_area` rung
- [x] 5.5 `study_area.js`: client refusal for point / line / polygon placement and crosshair; spray dots outside dropped; message shown
- [x] 5.6 Section POST: PostGIS check (point within; line/polygon covered by area + 5 m), skip + log + `refused_marks`; spray clipped; object answers unchecked
- [x] 5.7 Translation table occurrence `survey:study_area_message`; gap engine counts it
- [x] 5.8 Tests in `survey/tests/test_survey_study_area.py`: place lookup (mocked), street → 100 m corridor and rebuilt at 50 m, point → rectangle, service down, upload reprojected, fog metadata, scripted outside point refused with normal next page, line 3 m outside accepted, rule off, translated message

## 6. Publish check, print, archive

- [x] 6.1 Publish / Publish changes dialog: study area row, linked layers with use and scope, "on no map" warning with inline fixes, scheduled-survey note with respondent preview link
- [x] 6.2 Printable form: frame on the study area, outline and grey outside, only placed layers
- [x] 6.3 Serialization: `placements` and `study_area` export/import; legacy `hidden_layers` and legend-only questions converted on import
- [x] 6.4 Tests in `test_survey_serialization.py` and `test_printable_form.py`
- [x] 6.5 Responses map: study-area outline layer (gated endpoint, no fog, under answers, "Study area" in the layers control)
- [x] 6.6 Reports map block: `payload['study_area']` from the own question's survey, `config.study_area` switch in the panel (`clean_config('map')`, default not stored), shared renderer + `pdf.map_image` draw it, frame/extent and `checks` untouched
- [x] 6.7 REST/MCP `update_block` accepts `study_area`, `get_report` returns it; regenerate references
- [x] 6.8 Tests: outline on Responses (in `test_survey_study_area.py`), report block payload/PDF/switch in the reports capability modules, API strict field

## 7. API and MCP parity

- [x] 7.1 REST v1: placement and study-area routes over the services (`extra='forbid'` schemas, role + Pro gates); regenerate `reference/api.md`
- [x] 7.2 MCP tools `place_layer`, `unplace_layer`, `get_study_area`, `set_study_area`, `clear_study_area` (confirm not needed: reversible); regenerate `reference/mcp-tools.md`
- [x] 7.3 `api/tests`, `mcp/tests` modules for both

## 7b. The Wizard sets the study area (owner, 2026-11-24)

- [x] 7b.1 Org-level `editor_place_boundary` endpoint over `study_area_lookup` (search + outline, width), rate-limited
- [x] 7b.2 Create page: prefill ranks every candidate by place type (fixes "Снега" → Arkhyz); boundary drawn with fog on the create map; "Study area" strip with Edit outline, corridor width, Allowed / Not allowed, Remove; hidden fields
- [x] 7b.3 Generation and the empty-survey path apply `study_area_mode` (`set` / `auto` from the model's location / `off`); lookup outside the transaction, failures ignored
- [x] 7b.5 The Wizard names the survey: `survey_name` in the schema and prompt, normalised in the validator, replaces a name derived from the goal (owner, 2026-11-24)
- [x] 7b.4 Tests in `test_ai_survey_generation.py` (set / auto / off / lookup down) and the endpoint; strings in the ten catalogs; help page section

## 8. Events, docs, release

- [x] 8.1 Creator events `layer_added`, `layer_placed`, `study_area_set`, `publish_check_shown`; none on respondent pages
- [x] 8.2 Help pages (reference layers rewritten, study area new) and `help_links` registry; screenshots
- [x] 8.3 What's new entry (`survey/changelog/`), hero tier for study area if the owner agrees; new strings in every offered catalog
- [x] 8.4 Full suite once (`./run_tests.sh survey billing api mcp newsletter`), `/verify` on a seeded survey (Map card, study area editor, respondent fog + refusal)
- [ ] 8.5 Offer commit / push / PR 1

## 9. Follow-up release (PR 2)

- [ ] 9.1 Delete legend-only `layer_objects` questions in every header; drop `Question.panel_mode`, `SurveySection.hidden_layers` and `SurveyMapLayer.show_tallies` / `show_comments` (moved from `layers-by-question`)
- [ ] 9.2 Remove the PR 1 hiding shims and their tests; archive the change
