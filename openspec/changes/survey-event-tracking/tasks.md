## 1. Model and Migration

- [x] 1.1 Add `EVENT_TYPE_CHOICES` tuple and `SurveyEvent` model to `survey/models.py` after `SurveySession` class
- [x] 1.2 Write migration `0021_add_survey_event.py` — create table with composite indexes `(session, event_type)` and `(session, created_at)`
- [x] 1.3 Run `python manage.py makemigrations` and verify migration generated

## 2. Event Emission Module

- [x] 2.1 Create `survey/events.py` with `emit_event(session, event_type, metadata)` — fire-and-forget, swallows exceptions
- [x] 2.2 Add `build_session_start_metadata(request)` — extracts user_agent ([:512]) and referrer
- [x] 2.3 Add `_classify_referrer(raw_referrer)` — returns (host, bucket) where bucket is google/social/email/direct/other

## 3. Event Emission in Views

- [x] 3.1 Import `emit_event`, `build_session_start_metadata` in `survey/views.py`
- [x] 3.2 Emit `session_start` in `survey_section` after new SurveySession created (line ~337)
- [x] 3.3 Emit `session_start` in `survey_language_select` after SurveySession created (line ~267)
- [x] 3.4 Emit `section_view` in `survey_section` GET branch after session resolved
- [x] 3.5 Emit `section_submit` in `survey_section` POST branch after answers saved, before redirect
- [x] 3.6 Emit `survey_complete` in `survey_thanks` before `request.session.pop` calls

## 4. AJAX Page Load Endpoint

- [x] 4.1 Add `analytics_track_page_load` view to `survey/analytics_views.py` — csrf_exempt, require_POST, session ownership validation, cache rate limiting (10/hour)
- [x] 4.2 Add URL `surveys/track/page-load/` in `survey/urls.py` (before survey_slug catch-all)
- [x] 4.3 Add JS beacon snippet to `survey/templates/survey_section.html` — sendBeacon with fetch fallback, fire-and-forget

## 5. Performance Analytics Service

- [x] 5.1 Add `PerformanceAnalyticsService` class to `survey/analytics.py`
- [x] 5.2 Implement `get_event_summary()` — session_starts, completions, completion_rate, page_load_count, median_load_ms
- [x] 5.3 Implement `get_funnel()` — per-section views/submits/drop_rate in linked-list order
- [x] 5.4 Implement `get_referrer_breakdown()` — GROUP BY referrer_type from session_start metadata
- [x] 5.5 Implement `get_completion_by_referrer()` — started/completed/rate per referrer_type
- [x] 5.6 Implement `get_page_load_stats()` — avg/median per section from page_load metadata

## 6. Performance Tab View and Template

- [x] 6.1 ~~Add `analytics_performance` view~~ — decided to include data in analytics_dashboard view (no separate endpoint needed)
- [x] 6.2 Extend `analytics_dashboard` view to call `PerformanceAnalyticsService` and pass context
- [x] 6.3 Add tab bar (Responses | Performance) to `analytics_dashboard.html` with JS switchAnalyticsTab()
- [x] 6.4 Wrap existing dashboard content in `#pane-responses` div
- [x] 6.5 Create `survey/templates/editor/partials/analytics_performance.html` — summary cards, funnel chart (Chart.js), referrer table, completion by source table, page load stats

## 7. Tests

- [x] 7.1 `ReferrerClassificationTest` — google, direct, None, social/instagram, unknown, www prefix
- [x] 7.2 `EmitEventTest` — creates row, None session, swallows DB errors
- [x] 7.3 `EventIntegrationTest` — session_start on first visit, no duplicate on revisit, section_submit on POST, survey_complete on thanks, referrer capture
- [x] 7.4 `PageLoadTrackingTest` — valid payload → 204, mismatched session → 204, missing fields → 400, invalid load_ms → 400
- [x] 7.5 `PerformanceAnalyticsServiceTest` — event_summary counts, referrer breakdown, empty survey defaults, completion by referrer

## 8. Quality Review Fixes

- [x] 8.1 Fix JS beacon: use `performance.now()` relative to navigation start instead of `_t0` delta
- [x] 8.2 Fix JS fetch fallback: add `Content-Type: application/json` header
- [x] 8.3 Remove dead `analytics_performance` view and URL (data embedded in dashboard)
- [x] 8.4 Fix funnel bar width: use `{% widthratio %}` for percentage calculation
