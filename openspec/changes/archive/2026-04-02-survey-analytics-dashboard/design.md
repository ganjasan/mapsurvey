## Context

Survey creators currently have no analytics. The only data access is via CSV+GeoJSON download (`download_data` view) which dumps raw data. There is no aggregation, no completion tracking, no visual dashboards. `SurveySession.end_datetime` is never set by the codebase, so completion must be inferred from answer data.

The editor already provides a full-featured UI with auth (`@survey_permission_required`), HTMX partials, and Leaflet maps. The analytics dashboard extends this existing infrastructure.

## Goals / Non-Goals

**Goals:**
- Overview stats: total sessions, completed count, completion rate
- Daily response chart (Chart.js)
- Geo response map showing all point/line/polygon answers
- Per-question statistics: choice distributions, number aggregates, text answer pagination
- Accessible to all users with at least `viewer` role on the survey

**Non-Goals:**
- Event tracking / section-level funnel (Phase 2)
- Referrer / traffic source tracking (Phase 2)
- UTM parameters (Phase 3)
- A/B testing (Phase 4)
- Real-time updates / WebSocket
- Caching layer (add when needed)

## Decisions

### 1. Separate analytics service module (`analytics.py`)

All database queries live in `SurveyAnalyticsService` class, initialized with a `SurveyHeader`. Views are thin — they call service methods and pass results to templates. This makes queries reusable for future API endpoints, exports, or Phase 2+ extensions.

**Alternative considered**: Inline queries in view functions (fewer files). Rejected because query logic will grow with phases and should be testable independently.

### 2. Separate views module (`analytics_views.py`)

Analytics views live in their own module rather than being added to the already large `editor_views.py`. This follows the project's pattern of separating by domain (`org_views.py`, `editor_views.py`).

### 3. "Completed" = has answers in the last section

`SurveySession.end_datetime` is never populated. Completion is inferred by checking whether the session has at least one `Answer` whose `Question` belongs to the survey's last section (determined via `_get_sections_ordered()[-1]`).

**Alternative considered**: Any session with at least one answer = completed. Rejected because opening a survey and answering one question in section 1 of 5 is not "completed".

### 4. Show only current survey's data (no version aggregation)

Sessions are filtered by `survey=request.survey` (the specific SurveyHeader). In the versioning system, sessions stay bound to the version they were created under. Published versions contain all real data; old closed versions contain only test sessions.

### 5. Chart.js from CDN

Loaded via `{% block extra_head %}` — only on the analytics page, not globally. Chart.js v4 from jsDelivr (~60KB).

### 6. Template partials for each analytics section

5 partials included from the main template. Each partial is self-contained with its own `<script>` block for Chart.js/Leaflet initialization. This keeps the main template clean and makes partials individually replaceable.

### 7. HTMX server-side pagination for text answers

Text answers are loaded lazily via `hx-trigger="revealed"` and paginated server-side with configurable page size (10/20/50). This scales to any number of text responses without loading them all into the page.

### 8. GeoJSON from `.geojson` property

Use Django's `GEOSGeometry.geojson` property (returns GeoJSON string) rather than manual coordinate extraction. This is simpler and more correct than the pattern in `_export_survey_data` which manually builds coordinate arrays.

## Module Structure

```
survey/
├── analytics.py              # SurveyAnalyticsService (queries)
├── analytics_views.py         # 2 view functions
├── templates/editor/
│   ├── analytics_dashboard.html           # main page
│   └── partials/
│       ├── analytics_overview.html        # stat cards
│       ├── analytics_daily_chart.html     # Chart.js
│       ├── analytics_geo_map.html         # Leaflet map
│       ├── analytics_question_stats.html  # per-question
│       └── analytics_text_answers.html    # HTMX paginated
```

## Data Flow

```
GET /editor/surveys/<uuid>/analytics/
  → @survey_permission_required('viewer')
  → analytics_views.analytics_dashboard()
      → SurveyAnalyticsService(request.survey)
          .get_overview()            → {total, completed, rate}
          .get_daily_sessions()      → [{date, count}, ...]
          .get_geo_feature_collection() → GeoJSON FeatureCollection
          .get_all_question_stats()  → [{question, type, data}, ...]
      → json.dumps() for JS-consumed data
      → render('editor/analytics_dashboard.html', context)

GET /editor/surveys/<uuid>/analytics/questions/<id>/text/?page=2&page_size=20
  → @survey_permission_required('viewer')
  → analytics_views.analytics_text_answers()
      → SurveyAnalyticsService(request.survey)
          .get_text_answers(question, page=2, page_size=20)
      → render('editor/partials/analytics_text_answers.html', context)
```
