## Tasks

### Task 1: Service method `get_table_page()`

**File:** `survey/analytics.py`

Add to `SurveyAnalyticsService`:

1. Private method `_get_ordered_questions()` — returns flat list of top-level questions ordered by section linked-list + order_number. Each item: `{'key': str(q.id), 'label': q.name, 'input_type': q.input_type, 'question_id': q.id}`. Prepend 3 system columns: `{'key': 'id', 'label': '#', 'input_type': None}`, `{'key': 'start_datetime', 'label': 'Start time', 'input_type': None}`, `{'key': 'language', 'label': 'Language', 'input_type': None}`.

2. Private method `_format_cell(answer)` — format Answer to display string by input_type:
   - choice/multichoice/rating → `', '.join(get_selected_choice_names())`
   - number/range → `str(a.numeric)` or `"—"`
   - text/text_line/datetime → `a.text` or `"—"`
   - point → `f"{a.point.y:.2f}, {a.point.x:.2f}"`
   - line → `f"{len(a.line.coords)} vertices"`
   - polygon → `f"{len(a.polygon.exterior.coords) - 1} vertices"`

3. Public method `get_table_page(page, page_size, session_ids, sort_col, sort_dir, col_search)`:
   - Get columns via `_get_ordered_questions()`
   - Build session queryset filtered by `session_ids` if provided
   - If sorting by system column → queryset `order_by()`
   - If sorting by question column → Python sort (fetch answer values for sort column, sort session PKs, slice page)
   - Fetch page of session PKs
   - Bulk fetch all Answers for those sessions: `Answer.objects.filter(survey_session_id__in=page_pks, parent_answer_id__isnull=True).select_related('question')`
   - Pivot: `{session_id: {question_id: answer}}`
   - Build rows with formatted cell values
   - Apply col_search: Python filter on formatted values
   - Return dict: `{columns, rows, page, total_pages, total, page_size, sort_col, sort_dir, col_search}`

**Done when:** Method returns correct data for a survey with mixed question types. Manually testable via Django shell.

---

### Task 2: View and URL

**File:** `survey/analytics_views.py`, `survey/urls.py`

1. Add `analytics_table(request, survey_uuid)` view:
   - `@survey_permission_required('viewer')`
   - Parse GET params: `filters`, `page`, `sort`, `dir`, `search_*`
   - Reuse `_parse_filter_param` + `_resolve_filtered_session_ids`
   - Call `service.get_table_page()`
   - Render `editor/partials/analytics_table.html`

2. Add URL: `path('editor/surveys/<uuid:survey_uuid>/analytics/table/', analytics_views.analytics_table, name='analytics_table')`

**Done when:** GET request to URL returns HTML partial with table data.

---

### Task 3: Table partial template

**File:** `survey/templates/editor/partials/analytics_table.html` (new)

1. Toolbar row:
   - "Hide fields" button (toggles popover)
   - Fullscreen button (uses `requestFullscreen()` on `#pane-table`)
   - Badge: "N results"

2. Hidden state form `#table-state-form`:
   - Inputs: `filters`, `sort`, `dir`, `page`, `search_<col_key>` for each column
   - `hx-on::before-request` syncs `filters` from FilterManager

3. Table wrapper `<div class="attr-table-wrapper">` with `overflow-x: auto`:
   - `<table class="table table-sm table-bordered table-hover attr-table">`

4. Header row `<thead>`:
   - Each `<th data-col="col_key">`:
     - Column label (with input_type icon: `fa-map-marker` for point, `fa-draw-polygon` for polygon, `fa-route` for line, `fa-hashtag` for number, `fa-font` for text, `fa-list` for choice, `fa-clock` for datetime)
     - Sort toggle button (FA `fa-sort` / `fa-sort-up` / `fa-sort-down`)
     - Overflow menu button `...` → dropdown: Sort A→Z, Sort Z→A, Hide field, Freeze field
   - Search row: `<input>` per column with `hx-get`, `hx-trigger="input changed delay:500ms"`, `hx-target="#pane-table-content"`, `hx-include="#table-state-form"`

5. Body `<tbody>`:
   - Each `<tr>`:
     - First cell: eye button `<button onclick="loadSessionDetail({{ row.session_id }})">`
     - System cells: `#{{ row.id }}`, formatted datetime, language
     - Question cells: `{{ row.cells.col_key }}` with `data-col` attribute

6. Pagination:
   - "Page X of Y" text
   - Prev/Next buttons with `hx-get` including `page=N-1`/`page=N+1`, `hx-include="#table-state-form"`, `hx-target="#pane-table-content"`

7. "Hide fields" popover:
   - Absolute positioned div, list of columns with checkboxes
   - Toggle calls `setColHidden(key, bool)` JS function

**Done when:** Template renders a functional table with sort, search, pagination, eye button.

---

### Task 4: Dashboard integration

**File:** `survey/templates/editor/analytics_dashboard.html`, `survey/templates/editor/partials/analytics_geo_map.html`

1. **Tab bar**: Add "Table" button after "Performance" button.

2. **Pane shell**: Add `<div id="pane-table">` with `<div id="pane-table-content">` placeholder.

3. **Session detail modal**: Move `#sessionDetailModal` div from `analytics_geo_map.html` to `analytics_dashboard.html` (unconditional). Move/duplicate `loadSessionDetail()` function to dashboard scope.

4. **`switchAnalyticsTab('table')`**: On first activation, call `loadTable()`. Set `_tableLoaded = true`.

5. **`loadTable()` function**: Build URL with current FilterManager params, call `htmx.ajax('GET', url, {target: '#pane-table-content', swap: 'innerHTML'})`.

6. **FilterManager._updateTable**: Register as component. Guard on table visibility. Call `loadTable()`.

7. **Column state JS**:
   - `applyColState()` — reads localStorage, applies `.col-hidden` / `.col-frozen` CSS classes
   - `setColHidden(key, bool)` / `setColFrozen(key, bool)` — updates localStorage + live DOM
   - `htmx:afterSwap` listener on `#pane-table-content` → calls `applyColState()`

8. **CSS**:
   - `.attr-table-wrapper { overflow-x: auto; }`
   - `.attr-table th, .attr-table td { white-space: nowrap; max-width: 200px; overflow: hidden; text-overflow: ellipsis; }`
   - `.col-hidden { display: none !important; }`
   - `.col-frozen { position: sticky; left: 0; background: #fff; z-index: 2; }`
   - Table pane max-width: 1600px (wider than other panes' 1100px)

**Done when:** Table tab works end-to-end — click tab → loads table → sort/search/paginate → filters from Responses tab affect table → eye button opens session detail → column hide/freeze persists.
