## Why

Survey creators have zero visibility into how their surveys perform. The Lyon transit survey (bisqunours) has 562 sessions but only 98 completed — an 83% abandon rate — and the creator has no way to know this. There is no response count, no completion rate, no answer distributions, no map of geo responses. The only way to see results is to download a CSV+GeoJSON ZIP and analyze manually.

This is Phase 1 of the survey-analytics epic. It delivers a read-only analytics dashboard built entirely from existing data, requiring no database migrations.

## What Changes

- **Add** `survey/analytics.py` — `SurveyAnalyticsService` class with all query methods (overview, daily sessions, geo features, per-question stats, text answer pagination)
- **Add** `survey/analytics_views.py` — two view functions: full dashboard page + HTMX text answer pagination partial
- **Add** analytics dashboard template extending `editor/editor_base.html` with overview cards, Chart.js daily chart, Leaflet geo map, per-question stats (choice bar charts, number stats, text answer lists)
- **Add** 5 template partials: overview, daily chart, geo map, question stats, text answers (HTMX paginated)
- **Modify** `survey/urls.py` — add 2 URL patterns under `/editor/surveys/<uuid>/analytics/`
- **Modify** `survey/templates/editor/survey_detail.html` — add "Analytics" link in navbar

## Capabilities

### New Capabilities
- `survey-analytics-dashboard`: Read-only analytics page for survey creators showing response metrics, funnel overview, geo visualization, and per-question statistics

### Modified Capabilities
_(none — this is additive, no existing behavior changes)_

## Impact

- **Templates**: 6 new template files (1 page + 5 partials), 1 modified (survey_detail.html — add nav link)
- **Views**: New `analytics_views.py` module with 2 views
- **Service**: New `analytics.py` module with `SurveyAnalyticsService` class
- **URLs**: 2 new URL patterns
- **No database changes**: No migrations needed. Reads existing SurveySession, Answer, Question data
- **No new Python dependencies**: Chart.js loaded from CDN
- **Auth**: Uses existing `@survey_permission_required('viewer')` decorator
