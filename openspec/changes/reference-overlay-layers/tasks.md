# Tasks: reference-overlay-layers

## 1. Model & validation

- [x] 1.1 `SurveyMapLayer` model + `SurveySection.hidden_layers` JSONField; one additive
      migration (check leaf numbering vs master before merge).
- [x] 1.2 `survey/layers.py`: `validate_layer_upload()` (size, UTF-8, parse, normalize
      to FeatureCollection, WGS84 range check, feature cap, property-name union) +
      `MAP_REFERENCE_LAYERS` flag in settings.
- [x] 1.3 Tests (GIVEN/WHEN/THEN): valid upload, projected CRS rejected, oversize
      rejected, bare-geometry normalized, property union, re-serialization drops raw bytes.

## 2. Delivery endpoint

- [x] 2.1 `GET /surveys/<uuid>/layers/<id>.geojson` in `views.py`: same access gate as
      section pages, ETag from `updated_at`, `Cache-Control: private`, 304 support,
      404 when flag off.
- [x] 2.2 Tests: anonymous vs draft survey, published access, ETag 304, flag off.

## 3. Respondent rendering

- [x] 3.1 Layer metadata via `json_script` in `base_survey_template.html`; `_refLayers`
      init (dedicated pane under markers, simplestyle → fallback color, circleMarkers
      for points, escaped permanent labels, escaped popups when enabled,
      `interactive:false` otherwise); overlays registered in `L.control.layers`
      (control shown when basemaps > 1 or layers > 0).
- [x] 3.2 Per-section visibility: `data-hidden-layers` on `#section-data`
      (`survey_section_partial.html`), add/remove step in `initSection()`.
- [x] 3.3 Tests: metadata present on map sections, absent on form sections and when
      flag off; hidden-layers attribute reflects section config. Manual browser pass:
      tap-to-place over a polygon with popups on and off (desktop + mobile).

## 4. Editor

- [x] 4.1 Endpoints in `editor_views.py`: upload / update / delete (owner-only, JSON
      responses, human-readable 400s); section form POST accepts `hidden_layers`
      (unknown IDs dropped).
- [x] 4.2 "Reference layers" card in `survey_settings_panel.html` (+ full-page
      `survey_settings.html`): layer cards, edit state, upload zone, size/feature
      display; vanilla JS fetch, no reload. Template-comment guard test right after.
- [x] 4.3 Section checklist in `section_detail_form.html` between Layout and Button
      label; hidden on form layout / no layers / flag off.
- [x] 4.4 Tests: upload creates layer, config update persists, delete removes, section
      save filters unknown IDs, non-owner refused, flag off → 404 + no UI.

## 5. Serialization

- [x] 5.1 Export: `layers[]` in `serialize_survey_to_dict`, `layers/<pos>.geojson` via
      `zf.writestr`; `hidden_layers` position-indexes on sections.
- [x] 5.2 Import: `_clean_layer_config()`, recreate through `validate_layer_upload`,
      remap indexes → IDs, warnings on missing/invalid entries.
- [x] 5.3 Tests: round-trip (config + hidden section), legacy archive, corrupt entry warning.

## 6. Ship

- [x] 6.1 Full `./run_tests.sh survey`; template guard; check migration leaf vs master.
- [x] 6.2 Set up the Olney demo survey with the real 35-zone layer on the dev stand;
      manual desktop + mobile pass of the volunteer journey.
- [ ] 6.3 PR referencing this change; deploy behind flag (default on).
