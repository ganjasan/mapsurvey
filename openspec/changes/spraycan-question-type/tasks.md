## 1. Type sets and model

- [x] 1.1 `survey/question_types.py`: add `"spraycan"` to `GEO_TYPES`; add `GEO_COLUMNS`, `geo_column()`, `SPRAY_BRUSH_CHOICES`, `SPRAY_BRUSH_PX`, `SPRAY_HARD_CEILING`, `SHARED_MAP_SOURCE_TYPES = ("point","line","polygon")`; `PICKER_TYPES["spraycan"]` (group `geo`, `fas fa-spray-can`, label "Spray area", hint, example)
- [x] 1.2 `survey/models.py`: `INPUT_TYPE_CHOICES` entry `("spraycan", "Spray area")`; `Question.spray_brush`; `Answer.multipoint = MultiPointField(null=True, blank=True)`; `Answer.geometry` property; `SurveyHeader.geo_questions()` uses `GEO_TYPES`
- [x] 1.3 Migration `0092_spraycan` (two `AddField`, no data step)
- [x] 1.4 Replace every literal geo list with `GEO_TYPES` / `geo_column()` / `answer.geometry`: `views.py:888,891,1127,1154-1159`; `analytics.py:338,549,564,682-689,774-776,862,874,993,999,1016-1017,1670`; `public_results.py:39,286-294,305`; `export.py:76`; `ai/validator.py:17,102`; `editor_forms.py:375`; `editor_views.py:740,1559,1814` (keep `layers.py:592-607,733,742-754` on `SHARED_MAP_SOURCE_TYPES`, and `layers.py:643` on `answer.geometry`)
- [x] 1.5 Test: `GEO_TYPES` contains `spraycan`, `geo_column("spraycan") == "multipoint"`, `Answer.geometry` resolves per type

## 2. Respondent widget and paint mode

- [x] 2.1 `survey/forms.py`: `SprayDrawButtonWidget` (`draw_type="drawspray"`, template `spray_draw_button.html`, context `brush_px`, `max_dots`); `_get_form_from_input_type` branch (default icon `fas fa-spray-can`, no min/max features)
- [x] 2.2 `survey/templates/spray_draw_button.html` + `leaflet_draw_button.html`: `data-brush-px`, `data-max-dots` on the button
- [x] 2.3 New `survey/assets/js/spray_layer.js`: `L.SprayLayer` (canvas in overlayPane, `dots`, `redraw`, `toGeoJSON` → `Feature<MultiPoint>`, `getBounds`, `getCenter`, `hitTest`, no-op `editing`); include from `base_survey_template.html`, `question_preview_frame.html`, the two analytics dashboards
- [x] 2.4 `base_survey_template.html`: `#drawbar` tool segment (Spray / Erase / Move map), Clear; `.drawspray` handler → `startPaintMode(q, seedDots)`; pointer-event stroke engine (6 dots/tick, 60 ms dwell timer, uniform disc, cap + "brush is empty" hint); `endPaintMode(finish)` fires `draw:created` with `layerType:'spray'`; Cancel restores the previous layer; popup Edit re-enters paint mode; `startEditMode` skips layers without `.editing`; cancel paint mode when another draw/crosshair mode starts; `restoreGeoAnswers` `MultiPoint` branch
- [x] 2.5 `main.css`: `.spray-mode` cursor/ring, `touch-action: none`, drawbar segment styles; map-pane click on the cloud (hit test) opens the feature popup at `getCenter()`
- [x] 2.6 `i18n_extras.py` + locale catalogs: `spray`, `erase`, `moveMap`, `clear`, `brushEmpty`, spray tooltip (+ touch variant)
- [x] 2.7 `_build_section_context` (`views.py:877-920`) via `answer.geometry`; client validation counts a spray layer as one feature (`_geoLayersFor`)

## 3. Section POST

- [x] 3.1 `views.py:1127-1159`: `spraycan` branch — one chunk, `MultiPoint`, truncate to the creator cap or `SPRAY_HARD_CEILING`, discard non-finite / out-of-range coordinates with the geo validation error, `setattr(answer, geo_column(...), geom)`; sub-answers unchanged
- [x] 3.2 `layers.sync_question_layers_for_session` ignores spraycan questions
- [x] 3.3 Tests next to `GeoMultiFeatureTest` / `MalformedGeometryChunkTest`: store 120 dots; re-submit replaces; 3500 → 3000; `[200, 95]` refused; required with zero dots blocks; sub-question answers attach to the cloud row

## 4. Editor

- [x] 4.1 `question_form_modal.html`: `fg-spray_brush` (select), JS mirrors `SPRAY_TYPES`; `toggleTypeScopedFields` hides `fg-icon_class`, `toggleValidationFields` hides `#vs-geo-fields` for spraycan; `editor_views.editor_question_edit` saves `spray_brush`
- [x] 4.2 `editor_forms.py:12` and `editor_clipboard.js:25`: `spraycan` in the sub-question disallow list; `clean_layout` refuses form layout (via `GEO_TYPES`)
- [x] 4.3 `question_types.PICKER_TYPES` example + `question_type_picker.html`; `survey_filters.input_type_label`; `question_list_item.html` icon; `question_preview_frame.html` canned 150-dot cloud; `editor_question_preview_live` renders the spray button
- [x] 4.4 `_source_layers_of` / shared-map source picker stay on `SHARED_MAP_SOURCE_TYPES` (test: spraycan not offered)
- [x] 4.5 `cloning.py`: assert `spray_brush` copied (test with duplicate section / cross-survey paste)
- [x] 4.6 Update parity tests: `QuestionTypePickerMetadataTest`, `QuestionSubtextRenderingTest` `EXPECTED`, `ThumbsQuestionTest` / `MobileEditorNavTest` picker groups, `MaplessSection*` geo lists

## 5. Responses (analytics)

- [x] 5.1 `analytics.get_geo_feature_collection`: `MultiPoint` features with `properties.dots`; `_stats_geo` dispatch; `_format_cell` "N dots"; `format_session_answers` label "Spray cloud"; `analytics_table.html:226-228,255-257,566` icon/colour/filter for spraycan
- [x] 5.2 `analytics_geo_map.html` `LayerManager`: slot kind `spray` → `L.heatLayer` with weight `1/dots`; `createHeat`/heat menu skip spray slots; legend `geomIcons.MultiPoint`; rectangle/lasso selection tests the cloud centre; Map pane renders with spraycan as the only geo question
- [x] 5.3 `analytics_dashboard_v2.html:1196-1243`, `analytics_session_detail.html:138-185`, `analytics_overview_pane.html` thumbnail: `MultiPoint` branch → `L.SprayLayer` (dots) / heat on the thumbnail; drawer states the dot count
- [ ] 5.4 Tests (payload `dots` + cell format done in `SpraycanReadSurfacesTest`; drawer/detail/empty-state variants pending): `AnalyticsViewTest` / `ResponsesV2DrawerTest` / `SessionDetailViewTest` / `ResponsesMapEmptyStateTest` variants with a spray cloud; equal-weight assertion on the feature payload (`dots` present)

## 6. Export

- [x] 6.1 `export.py`: `EXPORT_GEOMETRY_TYPES` from `GEO_TYPES`; `GEOMETRY_TYPE_NAMES["spraycan"]="MultiPoint"`, `OGR_GEOMETRY_TYPES["spraycan"]="wkbMultiPoint"`; `_collect_part` reads `answer.geometry`, adds `dot_count` property; `observation_rows` centroid for MultiPoint; trailing `dot_count` column only when a spraycan question is in scope; xlsx sheet follows
- [x] 6.2 Tests in `ExportFormatsTest` / `ExportOgrFormatsTest`: GeoJSON feature per cloud with `dot_count`; observations row (`MultiPoint`, centroid, `MULTIPOINT (` wkt, last column); no `dot_count` column without spraycan; shp layer MULTIPOINT; gpkg/kml layer present

## 7. Public results

- [x] 7.1 `public_results.py`: `_map_payload` spraycan branch → EPSG 3857 grid (`cell = max(20 m, longer_side/40)`), distinct sessions per cell, drop `< k`, `data_type:'grid'`, `cells`, `max`, `respondents_total`, `cell_m`; `PUBLIC_RESULTS_SNAPSHOT_VERSION = 2`
- [x] 7.2 `public_results_editor.py`: no viz options / label fields for spraycan blocks; `editor/public_results.html` hides the checkboxes
- [x] 7.3 `public_results.html` `renderMap`: `grid` renderer (choropleth, opacity by `respondents/max`, total respondents caption)
- [x] 7.4 Tests in `PublicResultsServiceTest`: cell below k omitted; counts respondents not dots; payload has no MultiPoint / session ids; k=1 keeps all cells; stale snapshot shows the re-freeze notice

## 8. Serialization and AI

- [x] 8.1 `serialization.py`: `_serialize_question`/`_create_question` carry `spray_brush` (default `medium` + report line on unknown); `_serialize_answer`/`create_answer` carry `multipoint` WKT; tests in `StructureSerializationTest` / `DataSerializationTest`
- [x] 8.2 `ai/prompts.py`: type description + fuzzy-vs-bounded guidance; `ai/validator.py`: colour required, icon not; `ai/materialize.py`: default brush; one example brief chip; tests `AIValidatorTest` (two geo questions still fail) and `AIGeneratorKnowsEveryTypeTest` green; `_ai_question` helper uses `GEO_TYPES`

## 9. Ship

- [x] 9.1 `survey/changelog/<release-date>-spray-area-question.html` (kind `new`, screenshot of paint mode, mention re-freeze for frozen public pages)
- [x] 9.2 `CLAUDE.md`: one paragraph on `GEO_COLUMNS` / `answer.geometry` and `SHARED_MAP_SOURCE_TYPES` so the next geo type goes through the map, not a literal
- [x] 9.3 `./run_tests.sh survey` baseline before and after; `RepoHygieneTest` / template guard tests green
- [ ] 9.4 Browser check on desktop (DONE 2026-10-04 via Playwright: paint, erase, move, dwell, finish+popup, click-to-reopen, submit, Responses heat, drawer, public grid; fixed fit-to-cloud zoom and deferred heat canvas) and a phone (PENDING) (dev server, `PORT_OFFSET=530`): paint, erase, move, dwell density, cap hint, finish with sub-question popup, edit, delete, restore after re-open; Responses heat, drawer dots, export xlsx/gpkg/shp open in QGIS; public grid with k=3
- [ ] 9.5 PR with `[render preview]` in the title for a phone test on a Render preview
