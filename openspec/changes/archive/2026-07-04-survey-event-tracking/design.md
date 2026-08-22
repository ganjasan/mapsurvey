## Context

The analytics dashboard at `/editor/surveys/<uuid>/analytics/` renders response data: overview stats (total sessions, completed, rate), response timeline, geo map, and per-question charts with cross-filtering. All data comes from SurveySession + Answer models — there is no event tracking. SurveySession.end_datetime exists but is never written to. Completion is inferred by checking if a session has an answer in the last section.

Session creation happens in two places: `survey_section` (single-language, line 334) and `survey_language_select` (multilingual, line 265). Both store `survey_session_id` in `request.session`. The thanks page pops the session ID after rendering.

## Goals / Non-Goals

**Goals:**
- Track respondent behavior events (start, view, submit, complete, page load)
- Capture and classify referrer on session start
- Show funnel, traffic sources, and page load stats in a Performance tab
- Never break the survey respondent experience — all emission is fire-and-forget

**Non-Goals:**
- IP address tracking
- UTM parameters (Phase 3)
- A/B testing (Phase 4)
- Real-time event streaming
- Backfilling existing sessions

## Decisions

### 1. SurveyEvent model with session FK (SET_NULL)
**Choice**: Single append-only model with event_type enum and metadata JSONField. Session FK uses SET_NULL (not CASCADE).
**Why**: SET_NULL preserves event history when sessions are deleted (via `delete_survey` view which explicitly deletes sessions due to PROTECT FK). Metadata JSONField stores event-specific data (user_agent, referrer, load_ms, section_name) without schema changes per event type. Same pattern as `thanks_html` and `choices` JSONFields in the codebase.

### 2. Event emission in survey/events.py
**Choice**: Separate `events.py` module with `emit_event()`, `build_session_start_metadata()`, and `_classify_referrer()`. Called explicitly from views.
**Why**: Keeps views readable (one-liner calls), emission logic testable in isolation. Not using Django signals (adds indirection with no benefit) or middleware (event types differ per call-site within the same view function).

### 3. Referrer classification into buckets
**Choice**: Classify referrers into 5 buckets: google, social, email, direct, other. Store raw hostname + bucket in metadata.
**Why**: More analytically useful than raw URLs, simpler than maintaining a 20+ domain brand mapping. Bucket stored at write time so analytics queries are trivial GROUP BYs.

### 4. Performance tab as eager-rendered include
**Choice**: Tab toggle via JS class switching. Performance data loaded in the same `analytics_dashboard` view call and included via `{% include %}`. No HTMX lazy load.
**Why**: Performance data is aggregate counts (small), not per-answer rows. One view, one render — simpler than a separate endpoint. Tab switching is instant with no round-trip.

### 5. AJAX page_load endpoint with cache-based rate limiting
**Choice**: `@csrf_exempt @require_POST` endpoint at `/surveys/track/page-load/`. Session ownership validated via `request.session['survey_session_id']`. Rate limited to 10 events/hour/session using Django cache.
**Why**: Anonymous respondents have no CSRF token. Session ownership check prevents cross-session event injection. Cache rate limiting prevents abuse without adding a dependency. Mismatched session IDs return 204 silently (no info leakage).

### 6. PerformanceAnalyticsService in analytics.py
**Choice**: New service class in existing `analytics.py` alongside `SurveyAnalyticsService`.
**Why**: Same file, same pattern (pure service, no request knowledge, returns plain dicts). Not worth a separate file for one closely-related service.

## Component Interaction

```
Respondent browser
  ├─ GET /surveys/<slug>/<section>/
  │    └─ survey_section view
  │         ├─ [new session] → emit_event('session_start', metadata={referrer, user_agent})
  │         └─ emit_event('section_view', metadata={section_name})
  ├─ POST /surveys/<slug>/<section>/
  │    └─ survey_section view → save answers → emit_event('section_submit')
  ├─ GET /surveys/<slug>/thanks/
  │    └─ survey_thanks → emit_event('survey_complete')
  └─ JS sendBeacon → POST /surveys/track/page-load/
       └─ analytics_track_page_load → emit_event('page_load', metadata={load_ms})

Editor browser
  └─ GET /editor/surveys/<uuid>/analytics/
       └─ analytics_dashboard view
            ├─ SurveyAnalyticsService (existing — Responses tab)
            └─ PerformanceAnalyticsService (new — Performance tab)
                 ├─ get_event_summary() → summary cards
                 ├─ get_funnel() → section funnel chart
                 ├─ get_referrer_breakdown() → traffic sources table
                 ├─ get_completion_by_referrer() → CR by source
                 └─ get_page_load_stats() → load time stats
```
