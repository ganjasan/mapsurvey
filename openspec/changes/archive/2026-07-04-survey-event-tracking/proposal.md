## Why

The analytics dashboard shows response data (per-question stats, timeline, geo map) but has zero visibility into respondent behavior: where they drop off, how they found the survey, or how fast pages load. The Lyon transit survey (lead-035) had 562 sessions and only 98 completions — 83% abandon rate — and the creator had no way to see this funnel breakdown.

## What Changes

- **SurveyEvent model**: Append-only event log capturing session_start, section_view, section_submit, survey_complete, and page_load events with metadata JSONField.
- **Event emission in views**: Emit events at key points in the survey flow (session creation, section GET/POST, thanks page).
- **Referrer tracking**: Capture and classify HTTP_REFERER on session_start into buckets (google, social, email, direct, other).
- **Performance tab**: "Responses | Performance" tabs on the analytics dashboard. Performance tab shows funnel (section views vs submits + drop rate), traffic sources, completion rate by source, and page load stats.
- **Client-side page_load beacon**: Fire-and-forget JS snippet sends timing data via AJAX to a csrf_exempt endpoint.

## Capabilities

### New Capabilities

- `survey-event-model`: SurveyEvent model with session FK (SET_NULL), event_type enum, created_at, metadata JSONField. Append-only, never breaks survey UX.
- `event-emission`: `emit_event()` helper in `survey/events.py` that silently swallows all exceptions. `build_session_start_metadata()` extracts user agent and referrer. `_classify_referrer()` buckets domains.
- `performance-analytics-service`: `PerformanceAnalyticsService` in `analytics.py` with get_funnel(), get_referrer_breakdown(), get_page_load_stats(), get_completion_by_referrer(), get_event_summary().
- `performance-tab`: Responses | Performance tab UI on analytics dashboard. Funnel chart (Chart.js bar), referrer table, completion by source table, page load stats cards.
- `page-load-tracking`: Fire-and-forget JS beacon using navigator.sendBeacon/fetch with keepalive. CSRF-exempt endpoint with session ownership validation and cache-based rate limiting (10/hour).

### Modified Capabilities

- `analytics-dashboard`: Tab bar added, existing content wrapped in Responses tab pane. Performance data loaded eagerly in same view (small data volume).
- `survey-section-view`: Emits section_view event on GET, section_submit on POST, session_start on new session creation.
- `survey-thanks-view`: Emits survey_complete before clearing session.
- `survey-language-select`: Emits session_start for multilingual surveys.

## Impact

- **New files**:
  - `survey/events.py` — emit_event(), build_session_start_metadata(), _classify_referrer()
  - `survey/migrations/0021_add_survey_event.py` — SurveyEvent table + indexes
  - `survey/templates/editor/partials/analytics_performance.html` — Performance tab partial

- **Modified files**:
  - `survey/models.py` — add EVENT_TYPE_CHOICES + SurveyEvent model
  - `survey/analytics.py` — add PerformanceAnalyticsService class
  - `survey/analytics_views.py` — add analytics_performance view, analytics_track_page_load endpoint, extend analytics_dashboard context
  - `survey/views.py` — add emit_event calls at 5 insertion points
  - `survey/urls.py` — add 2 URL patterns
  - `survey/templates/editor/analytics_dashboard.html` — add tab bar + pane wrappers
  - `survey/templates/survey_section.html` — add page_load JS snippet
  - `survey/tests.py` — add 4 test classes

## Out of Scope

- IP address capture (privacy/GDPR)
- UTM parameter tracking (Phase 3)
- A/B testing (Phase 4)
- Per-section funnel with time-spent metrics (future iteration)
- Backfill of existing sessions — old sessions will have no events
- Referrer brand-level normalization (Instagram, X, etc.) — using bucket categories instead
