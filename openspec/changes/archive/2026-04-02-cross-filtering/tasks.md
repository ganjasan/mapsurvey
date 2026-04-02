## 1. Server: Analytics Service Extensions

- [x] 1.1 Add `get_answer_matrix()` to `SurveyAnalyticsService` — returns compact per-session choice data
- [x] 1.2 Add `session_id` to `get_geo_feature_collection()` feature properties
- [x] 1.3 Add `choice_codes_json` to `get_question_stats()` for choice-type questions
- [x] 1.4 Add `session_ids` param to `get_text_answers()` for filtered queries

## 2. Server: View Layer

- [x] 2.1 Add `_parse_filter_param()` helper to `analytics_views.py`
- [x] 2.2 Add `_resolve_filtered_session_ids()` helper to `analytics_views.py`
- [x] 2.3 Wire `answer_matrix_json` and `text_question_ids_json` into `analytics_dashboard` context
- [x] 2.4 Wire `filters` param into `analytics_text_answers` view

## 3. Template: Dashboard Shell

- [x] 3.1 Add CSS for filter pills, visual separator, section labels
- [x] 3.2 Add visual separator between general (overview+daily) and filterable (questions+map) blocks
- [x] 3.3 Add `<div id="filter-pills-bar">` container
- [x] 3.4 Embed answer matrix as `<script type="application/json">`
- [x] 3.5 Define `FilterManager` class inline
- [x] 3.6 Define `loadTextAnswers()` helper function
- [x] 3.7 Initialize global registries and `window.filterManager` on DOMContentLoaded

## 4. Template: Chart Interactivity

- [x] 4.1 Register each chart in `window.analyticsCharts` and codes in `window.analyticsChartCodes`
- [x] 4.2 Register choice labels in `window.analyticsChoiceLabels`
- [x] 4.3 Add `onClick` handler to each choice/rating chart
- [x] 4.4 Add `cursor: pointer` style on chart canvases

## 5. Template: Geo Map Filtering

- [x] 5.1 Restructure `L.geoJSON()` to per-session `L.layerGroup()` construction
- [x] 5.2 Populate `window.geoLayersBySid` and `window.geoGroup`

## 6. Template: Text Answer Filtering

- [x] 6.1 Update pagination buttons to use `loadTextAnswers()` instead of static `hx-get`
- [x] 6.2 Update page-size select to use `loadTextAnswers()`

## 7. Tests

- [x] 7.1 Test `get_answer_matrix()` returns correct structure
- [x] 7.2 Test `_parse_filter_param()` with valid and invalid inputs
- [x] 7.3 Test `_resolve_filtered_session_ids()` with single and multiple filters
- [x] 7.4 Test `get_text_answers()` with `session_ids` filter
- [x] 7.5 Test `analytics_text_answers` view with `?filters=` param
