## 1. Model and service

- [x] 1.1 `SectionStudyArea` model (survey FK, `section_ref`, `mode`, nullable geometry, source, place_name, osm_ref, fog, refuse_outside, message, refused_marks, updated_at; unique survey+ref) + migration
- [x] 1.2 Service: `section_row`, `section_mode`, `effective(section)`, `set_section_area`, `update_section_settings`, `set_section_mode`, `set_section_message_translation`, `section_choices(survey)`; `count_refused` on the refusing area; audit + `study_area_set` event with `scope`
- [x] 1.3 Tests (`test_survey_study_area.py`): default, own, none, restore, draft copy writes canonical, own without outline refused, mapless refused

## 2. Respondent, guard, preview

- [x] 2.1 `views.study_area_meta(section)` → effective meta; template filter on `#section-data[data-study-area]`; drop the shell `json_script`
- [x] 2.2 Outline endpoint `?section=<id>` serves an own area (section must belong to the survey)
- [x] 2.3 `study_area.js` `show(map, meta)` swaps/clears; `initSection()` calls it on map sections and re-opens on a changed area
- [x] 2.4 `study_area_guard.for_section` uses the effective area
- [x] 2.5 Live preview carries the section's meta
- [x] 2.6 Tests: swap metadata per section, POST on No area / own area, preview, endpoint gating

## 3. Editor UI

- [x] 3.1 Study area editor + save/settings/clear/from_layer accept `section`; editor page names the section, prefills from the survey's outline, Back to the section, Remove → survey's area
- [x] 3.2 `editor_study_area_section_mode` endpoint (survey / own / none)
- [x] 3.3 Map card: three radios with summaries
- [x] 3.4 Survey settings → Respondent map: study area summary, Set/Edit, Remove (Dialog.confirm), fog and refusal switches
- [x] 3.5 Tests (`test_survey_study_area.py`, next to the parent change's editor tests): Map card choices, settings card, section editor writes

## 4. Translations, archive, copies, print

- [x] 4.1 Translation occurrence `section:<ref>:study_area_message` + writer + gaps + link
- [x] 4.2 ZIP `section_study_areas` export/import with report lines; copies (`cloning.py`)
- [x] 4.3 Print: `resolve_frame` / `draw_study_area` per section; form hash includes overrides
- [x] 4.4 Tests in `test_survey_study_area.py` (archive, copy, translations, like the parent change) and `test_printable_form.py`

## 5. REST and MCP

- [x] 5.1 REST `GET/PUT /surveys/{uuid}/sections/{section_id}/study-area`; `get_study_area` lists `sections`
- [x] 5.2 MCP `get_section_study_area`, `set_section_study_area`; `get_study_area` lists `sections`
- [x] 5.3 Regenerate `reference/api.md`, `reference/mcp-tools.md`; tests in `api/tests/test_v1_map.py`, `mcp/tests/test_map.py`

## 5b. Place search: places first (owner, 2026-11-24)

- [x] 5b.1 `map_place_search.js`: first request `types=` places only, areas before streets, language of the query's alphabet; when no place answers, Mapbox all types + Photon in parallel, Photon areas first, Photon POIs above look-alikes
- [x] 5b.3 Rank by name match, then distance, only from a centre that means something (`rankFromCentre`; create page: not from `country` / `world` until moved, located or placed from the brief); areas keep the provider's order
- [x] 5b.4 "More results" row after a places answer: Mapbox `types=poi` + OSM, appended; "More results" in all 75 catalogs (respondent string); OSM `lang=default` for local names, OSM areas named like a listed area dropped
- [x] 5b.2 Check in the browser: «Санкт-Петербург», «Москва», «Дворцовая площадь», «Василеостровский район», «Школа 64», «Бишкек»

## 6. Docs and release

- [x] 6.1 Help page "Set the study area" (Survey settings, section choice); `.claude/architecture/map-layers.md`
- [x] 6.2 New creator strings in every catalog; What's new card of the study area epic amended
- [x] 6.3 Touched test modules, then the full suite once; `/verify` (settings card, Map card, respondent swap)
- [ ] 6.4 Offer commit / push / PR; archive after `map-layers-study-area`
