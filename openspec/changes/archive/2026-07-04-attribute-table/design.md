## Context

The analytics dashboard has two tabs (Responses, Performance) in `analytics_dashboard.html`. Responses tab contains overview cards, daily chart, geo map (with LayerManager), and question stats — all on one scrollable page. FilterManager coordinates cross-filtering between charts, map, and text answers. HTMX is used for text answer pagination and session detail loading. All JS is inline in Django templates.

## Goals / Non-Goals

**Goals:**
- Add Table tab with attribute table showing all sessions × questions
- Server-side pagination, sort, per-column search via HTMX
- Column hide/freeze via localStorage
- FilterManager integration (bidirectional with Responses tab)
- Reuse existing session detail modal

**Non-Goals:**
- Editing answers (read-only table)
- Validation/moderation UI
- IDE-style resizable panels (future task #46)
- New database models or migrations

## Decisions

### 1. Server-side rendering via HTMX (not client-side JS table)

Data can have many columns (10+ questions) × many rows (1000+ sessions). A JS-rendered table would require loading all data into the browser. Instead: each sort/filter/page change is a GET to `analytics_table` view, which returns a rendered HTML partial. HTMX swaps `#pane-table-content`.

This matches the existing pattern used by `analytics_text_answers` — server renders partial, HTMX swaps target.

### 2. Two-query data fetch (anti-N+1)

1. Fetch page of session PKs (with pagination/sort applied)
2. Bulk fetch all Answers for those session PKs in one query
3. Pivot in Python: `{session_id: {question_id: answer}}`

This avoids N+1 queries. The queryset for step 2 uses `select_related('question')`.

### 3. Column ordering from section linked-list

Reuse `_get_ordered_sections()` from analytics.py. Questions sorted by `(section_position, order_number)`. System columns prepended: ID, Start time, Language.

### 4. Geo value formatting

- Point: `"42.88, 74.60"` (lat, lng with 2 decimals)
- Line: `"5 vertices"`
- Polygon: `"12 vertices"`

Using `answer.point.y` (lat) / `answer.point.x` (lng), `len(answer.line.coords)`, `len(answer.polygon.exterior.coords) - 1`.

### 5. Sort on question columns

Sorting by a question column requires Python-side sort (answers in separate table). Approach: fetch all matching session IDs, fetch answer values for sort column, sort in Python, take page slice. Sessions without an answer for that question sort last.

Sort by system columns (id, start_datetime) uses queryset `order_by()` — fast.

### 6. Column hide/freeze (client-side only)

localStorage key: `attrTable_<survey_uuid>` → `{hidden: [col_keys], frozen: [col_keys]}`.

After every HTMX swap, `htmx:afterSwap` on `#pane-table-content` re-applies column state via CSS classes:
- `.col-hidden { display: none; }`
- `.col-frozen { position: sticky; left: 0; background: #fff; z-index: 2; }`

Column header dropdown (Sort/Hide/Freeze) is a small inline dropdown built in the template.

### 7. FilterManager integration

Register `_updateTable` as FilterManager component (same pattern as `_updateTextAnswers`). When filters change:
1. Guard: is table tab visible? If not, skip.
2. Call `loadTable()` which does `htmx.ajax('GET', url + '?filters=' + fm.getFilterParam(), ...)`

Table view reuses `_parse_filter_param()` and `_resolve_filtered_session_ids()` from analytics_views.py.

### 8. Session detail modal moved to dashboard

Currently the modal and `loadSessionDetail()` live inside `analytics_geo_map.html` (conditionally included only when geo features exist). Move both to `analytics_dashboard.html` so Table tab can use them unconditionally.

### 9. State management via form

A hidden `<form id="table-state-form">` holds current state (filters, sort, dir, page, per-column search values). HTMX requests use `hx-include="#table-state-form"`. Before each request, a `hx-on::before-request` handler syncs the `filters` hidden input from `FilterManager.getFilterParam()`.

## Component Architecture

```
analytics_dashboard.html
├── Tab bar: [Responses] [Performance] [Table]
├── #pane-responses (existing)
├── #pane-performance (existing)
├── #pane-table (new)
│   └── #pane-table-content (HTMX swap target)
│       └── analytics_table.html partial (swapped on every interaction)
│           ├── Toolbar: hide-fields btn, fullscreen btn, count badge
│           ├── State form (hidden inputs)
│           ├── Table wrapper (overflow-x: auto)
│           │   └── <table>
│           │       ├── <thead> — column headers with sort/menu
│           │       └── <tbody> — session rows with eye button
│           └── Pagination controls
├── #sessionDetailModal (moved from geo_map, unconditional)
├── FilterManager (extended with _updateTable)
└── Column state JS (applyColState, setColHidden, setColFrozen)
```

## Service Method

```python
class SurveyAnalyticsService:
    def get_table_page(self, page=1, page_size=50, session_ids=None,
                       sort_col=None, sort_dir='asc', col_search=None):
        """
        Returns one page of session rows with formatted answer values.

        Args:
            session_ids: Set of session PKs to include (from FilterManager), or None for all
            sort_col: 'id', 'start_datetime', 'language', or str(question_id)
            sort_dir: 'asc' or 'desc'
            col_search: dict {col_key: search_string} for per-column text filter

        Returns:
            dict with columns, rows, page, total_pages, total, page_size, sort_col, sort_dir
        """
```

## View Function

```python
@survey_permission_required('viewer')
def analytics_table(request, survey_uuid):
    survey = request.survey
    service = SurveyAnalyticsService(survey)

    # Parse filter param (reuse existing)
    filter_map = _parse_filter_param(request.GET.get('filters', ''))
    session_ids = _resolve_filtered_session_ids(survey, filter_map) if filter_map else None

    # Parse table params
    page = int(request.GET.get('page', 1))
    sort_col = request.GET.get('sort', 'start_datetime')
    sort_dir = request.GET.get('dir', 'desc')
    col_search = {k[7:]: v for k, v in request.GET.items() if k.startswith('search_') and v}

    result = service.get_table_page(
        page=page, session_ids=session_ids,
        sort_col=sort_col, sort_dir=sort_dir, col_search=col_search
    )

    return render(request, 'editor/partials/analytics_table.html', {
        'survey': survey, **result
    })
```
