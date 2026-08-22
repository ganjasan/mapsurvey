## 1. Model & Migration

- [x] 1.1 Add `BASEMAP_CHOICES` constant to `survey/models.py`
- [x] 1.2 Add `basemaps = models.JSONField(default=list)` to `SurveyHeader`
- [x] 1.3 Create migration

## 2. Reusable JS Partial

- [x] 2.1 Create `survey/templates/partials/basemap_layers.html` with IIFE

## 3. Wire Partial into All 4 Maps

- [x] 3.1 `base_survey_template.html`: replace `L.tileLayer` block with `{% include %}`
- [x] 3.2 `section_map_picker.html`: add mapboxUrl/mapboxAccessToken JS vars, replace `L.tileLayer` with `{% include %}`
- [x] 3.3 `analytics_geo_map.html`: add JS vars, replace `L.tileLayer` with `{% include %}`
- [x] 3.4 `analytics_session_detail.html`: add JS vars, replace `L.tileLayer` with `{% include %}`

## 4. Editor Settings UI

- [x] 4.1 `editor_forms.py`: add `basemaps` to SurveyHeaderForm fields + HiddenInput widget
- [x] 4.2 `editor_views.py`: pass `BASEMAP_CHOICES` in context for settings view
- [x] 4.3 `survey_settings.html`: add checkbox picker for basemaps

## 5. Serialization & Versioning

- [x] 5.1 `serialization.py`: add `basemaps` to export and import
- [x] 5.2 `versioning.py`: copy `basemaps` in clone and publish

## 6. Tests

- [x] 6.1 Test: basemaps field defaults to empty list, respondent page shows streets tile URL
- [x] 6.2 Test: survey with `basemaps=["satellite","topo"]` renders Esri and OpenTopoMap URLs
- [x] 6.3 Test: export/import preserves basemaps
- [x] 6.4 Test: clone_survey_for_draft copies basemaps
