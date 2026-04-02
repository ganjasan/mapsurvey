## 1. Analytics Service

- [x] 1.1 Create `survey/analytics.py` with `SurveyAnalyticsService` class, init with `SurveyHeader`
- [x] 1.2 Implement `_resolve_last_section(survey)` helper — reuse `_get_sections_ordered` pattern
- [x] 1.3 Implement `get_overview()` → `{total_sessions, completed_count, completion_rate}`
  - Total: `SurveySession.objects.filter(survey=).count()`
  - Completed: sessions with answers in last section (distinct count via subquery)
  - Rate: `completed / total * 100` (0 if no sessions)
- [x] 1.4 Implement `get_daily_sessions()` → list of `{date, count}` dicts
  - Use `TruncDate('start_datetime')`, `values('date')`, `annotate(count=Count('id'))`, `order_by('date')`
- [x] 1.5 Implement `get_geo_feature_collection()` → GeoJSON FeatureCollection dict
  - Query all geo answers across all geo questions, use `.geojson` property
  - Add `question_name` and `input_type` to feature properties
  - Optimize: single query with `select_related('question')` instead of per-question loop
- [x] 1.6 Implement `get_question_stats(question)` → stat dict dispatched by input_type
  - choice/multichoice/rating: count each code from `selected_choices`, resolve labels via `get_choice_name()`
  - number/range: `Avg`, `Min`, `Max`, `Count` aggregates + `statistics.median` on values list
  - text/text_line: count only (bodies paginated separately)
  - point/line/polygon: feature count only
- [x] 1.7 Implement `get_all_question_stats()` → ordered list of stat dicts for all top-level questions
- [x] 1.8 Implement `get_text_answers(question, page, page_size)` → paginated dict with answers, page info

## 2. Views

- [x] 2.1 Create `survey/analytics_views.py`
- [x] 2.2 Implement `analytics_dashboard` view — `@survey_permission_required('viewer')`, init service, call all methods, serialize JSON for charts/map, render template
- [x] 2.3 Implement `analytics_text_answers` view — HTMX partial, validate question belongs to survey, paginate, render partial

## 3. URLs

- [x] 3.1 Add `from . import analytics_views` to `survey/urls.py`
- [x] 3.2 Add URL: `editor/surveys/<uuid:survey_uuid>/analytics/` → `analytics_dashboard`
- [x] 3.3 Add URL: `editor/surveys/<uuid:survey_uuid>/analytics/questions/<int:question_id>/text/` → `analytics_text_answers`

## 4. Templates

- [x] 4.1 Create `survey/templates/editor/analytics_dashboard.html` — extends `editor_base.html`, Chart.js CDN in `extra_head`, navbar with clickable survey name, includes 4 partials
- [x] 4.2 Create `partials/analytics_overview.html` — 3 stat cards (sessions, completed, rate)
- [x] 4.3 Create `partials/analytics_daily_chart.html` — Chart.js bar chart with `daily_data_json`
- [x] 4.4 Create `partials/analytics_geo_map.html` — Leaflet map with GeoJSON layer, color by question, fitBounds
- [x] 4.5 Create `partials/analytics_question_stats.html` — loop question_stats: bar charts for choices, stat row for numbers, HTMX trigger for text, count for geo
- [x] 4.6 Create `partials/analytics_text_answers.html` — paginated text list, page size selector, prev/next buttons, all HTMX-powered

## 5. Integration

- [x] 5.1 Add "Analytics" link to `survey/templates/editor/survey_detail.html` navbar
- [x] 5.2 Add "Analytics" link to `survey/templates/editor.html` dashboard table
- [x] 5.3 Verify with PostGIS test database — 428 tests pass, 10 new analytics tests

## 6. Tests

- [x] 6.1 Test `SurveyAnalyticsService.get_overview()` — GIVEN survey with sessions and answers WHEN called THEN returns correct counts
- [x] 6.2 Test `get_overview()` with empty survey — GIVEN survey with no sessions WHEN called THEN returns zeros
- [x] 6.3 Test `get_daily_sessions()` — GIVEN sessions on different days WHEN called THEN returns correct daily counts
- [x] 6.4 Test `get_question_stats()` for choice question — GIVEN choice answers WHEN called THEN returns correct distribution
- [x] 6.5 Test `get_question_stats()` for number question — GIVEN numeric answers WHEN called THEN returns correct avg/median/min/max
- [x] 6.6 Test `get_text_answers()` pagination — GIVEN 25 text answers WHEN page=2 page_size=10 THEN returns answers 11-20
- [x] 6.7 Test analytics dashboard view auth — GIVEN unauthenticated user WHEN GET analytics THEN redirect to login
- [x] 6.8 Test analytics dashboard view renders — GIVEN authenticated viewer WHEN GET analytics THEN 200 with expected context
