## Context

The analytics dashboard (`/editor/surveys/<uuid>/analytics/`) currently renders:
- Overview stat cards (total sessions, completed, completion rate)
- Daily responses bar chart (Chart.js)
- Geo response map (Leaflet + GeoJSON)
- Per-question stats: horizontal bar charts for choice/multichoice/rating, numeric summaries, HTMX-loaded text answers

All data is aggregated server-side in `SurveyAnalyticsService` and passed as JSON to inline `<script>` blocks. No JS build system — everything is inline in Django templates.

## Goals / Non-Goals

**Goals:**
- Click a bar in a choice/rating chart → toggle filter → all other charts, geo map, and text answers update
- Multiple simultaneous filters across questions (AND logic between questions, OR within a question)
- Filter pills with individual remove and "Clear all"
- Overview cards + daily chart remain unfiltered, visually separated
- Instant client-side updates for charts and map
- Server-side filtering for text answers (HTMX with filter params)

**Non-Goals:**
- Number/range question filtering
- Date range filtering
- Filter state in URL / shareable links
- Overview stats recalculation on filter

## Decisions

### 1. Hybrid client/server filtering
**Choice**: Client-side for charts + geo map, server-side for text answers.
**Why**: Charts and map need instant feedback. Text data is paginated and potentially large — sending it all to the client would bloat the payload. HTMX already handles text answer loading.

### 2. Answer matrix payload
**Choice**: Server emits a compact JSON array of `{sid, date, answers: {qid: [codes]}}` for all sessions with choice/rating answers.
**Why**: This is the minimal data needed for client-side recomputation. At 1000 sessions x 5 questions ≈ 80KB uncompressed, acceptable for typical survey scale.

### 3. Geo filtering via session-grouped layers
**Choice**: Group Leaflet layers by session_id. Show/hide entire session layer groups.
**Why**: Simpler than re-rendering GeoJSON. Leaflet's `addLayer`/`removeLayer` is efficient.

### 4. Filter semantics
**Choice**: OR within a question (any selected code matches), AND across questions (session must match all).
**Why**: Standard cross-filter behavior. "Show me sessions where Age is 25-34 OR 35-44, AND Gender is Female."

### 5. No animation on chart update
**Choice**: `chart.update('none')` to skip Chart.js animation.
**Why**: Multiple charts update simultaneously — cascading animations feel sluggish.

## Data Structures

### Answer Matrix (server → client)
```json
[
  {"sid": 42, "d": "2024-01-15", "a": {"7": [1, 3], "12": [2]}},
  {"sid": 43, "d": "2024-01-16", "a": {"7": [2], "12": [1, 3]}}
]
```

### GeoJSON Feature Properties (extended)
```json
{"question": "Location", "type": "point", "session_id": 42}
```

### Filter State (client-side)
```js
// Map<questionId:string, Set<choiceCode:number>>
filters = new Map([["7", new Set([1, 3])]])
```

### Filter URL Param (for HTMX text answers)
```
?filters=7:1,3;12:2
```

## Component Design

### FilterManager (JS class, inline in analytics_dashboard.html)
- `toggleFilter(qid, code)` — add/remove filter, recompute all
- `clearAll()` — remove all filters
- `getFilterParam()` — serialize to URL param string
- `_recompute()` — iterate matrix, build `filteredSids: Set<int> | null`
- `_updateCharts()` — for filter-source chart: preserve original data, only highlight selected bar; for other charts: recount from matrix and update
- `_updateGeoMap()` — show/hide per-session layer groups
- `_updatePills()` — rebuild filter pills HTML
- `_updateTextAnswers()` — call `loadTextAnswers()` for each text question

### Global Registries (window.*)
- `analyticsCharts: Map<qid, Chart>` — chart instances
- `analyticsChartCodes: Map<qid, number[]>` — choice codes per chart
- `analyticsChoiceLabels: Map<"qid:code", string>` — labels for pills
- `geoLayersBySid: Map<sid, L.LayerGroup>` — geo layers per session
- `geoGroup: L.LayerGroup` — master geo layer group

### Server-side filter resolution (analytics_views.py)
- `_parse_filter_param(str)` → `{qid: [codes]}`
- `_resolve_filtered_session_ids(survey, filter_map)` → `set<sid>` using `Q(selected_choices__contains=[code])` OR queries per question, intersected across questions
