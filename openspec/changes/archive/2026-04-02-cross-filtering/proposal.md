## Why

The analytics dashboard shows aggregate statistics for all survey responses, but there's no way to explore relationships between questions. For example, a researcher can't see "how did people who answered 'Yes' to question A respond to question B?" This is a fundamental capability for survey analysis — known as cross-filtering or coordinated multiple views (CMV).

## What Changes

- Add interactive cross-filtering to the existing analytics dashboard
- Click a bar in any choice/multichoice/rating chart to filter all other visualizations
- Filter pills UI to show active filters with toggle and "Clear all"
- Visual separation: overview stats + daily chart (unfiltered) vs. question charts + geo map + text answers (filterable)
- Client-side filtering for charts and geo map (instant, no server round-trip)
- Server-side filtering for text answers via HTMX (text data too large for client)

## Capabilities

### New Capabilities

- `cross-filtering`: Interactive coordinated filtering across all analytics visualizations — choice charts, geo map, and text answers update simultaneously when a filter is toggled on any choice/rating chart bar.

### Modified Capabilities

- `analytics-dashboard`: Extended with answer matrix JSON payload, session IDs in geo features, and filter-aware text answer endpoint.

## Impact

- **Modified files**:
  - `survey/analytics.py` — new `get_answer_matrix()`, modify `get_geo_feature_collection()`, `get_question_stats()`, `get_text_answers()`
  - `survey/analytics_views.py` — filter parsing helpers, wire matrix to dashboard context, filter params in text endpoint
  - `survey/templates/editor/analytics_dashboard.html` — FilterManager JS class, visual separator, filter pills container
  - `survey/templates/editor/partials/analytics_question_stats.html` — chart registry, onClick handlers
  - `survey/templates/editor/partials/analytics_geo_map.html` — per-session layer groups
  - `survey/templates/editor/partials/analytics_text_answers.html` — filter-aware pagination

## Out of Scope

- Filtering by number/range questions (complex UX, deferred to v2)
- Filtering overview stats or daily chart
- Date range filtering
- URL-based filter persistence / shareable filter state
