## Why

The analytics dashboard shows aggregated views (charts, map) but no way to see individual responses in a table format. Researchers must export data to QGIS/Excel to inspect individual sessions, see raw values, or find specific responses. This breaks the workflow — data leaves Mapsurvey for basic inspection tasks.

## What Changes

- **Table tab** in Analytics: third tab alongside Responses and Performance. KoBoToolbox-style attribute table where each row is a session and each column is a question.
- **Server-side pagination, sort, search**: HTMX-powered — each interaction fetches a new page from the server.
- **Column management**: hide/freeze columns (client-side, localStorage), column header dropdown menus.
- **FilterManager integration**: filters applied in Responses tab (choice clicks, map selection, timeline range) automatically filter the Table tab.
- **Session detail modal**: eye button on each row opens the existing session detail modal.

## Capabilities

### New Capabilities

- `attribute-table`: Server-side rendered table of all sessions × questions. Columns ordered by section linked-list + order_number. Geo values shown as coordinates/vertex count. System columns: ID, start time, language. Server-side pagination (50/page), sort (A→Z/Z→A per column), per-column text search.
- `column-management`: Client-side column hide/freeze via localStorage. "Hide fields" popover to manage visibility. Column header dropdown with Sort/Hide/Freeze. Toggle fullscreen.
- `table-filter-integration`: Table registered as FilterManager component. Filter changes in Responses tab trigger table reload with filtered session IDs.

### Modified Capabilities

- `session-detail-modal`: Modal moved from geo_map partial to dashboard template (unconditional), so it works from Table tab even without geo questions. `loadSessionDetail()` function made global.

## Impact

- **New files**:
  - `survey/templates/editor/partials/analytics_table.html` — complete table partial
- **Modified files**:
  - `survey/analytics.py` — add `get_table_page()` method to SurveyAnalyticsService
  - `survey/analytics_views.py` — add `analytics_table()` view
  - `survey/urls.py` — register analytics_table URL
  - `survey/templates/editor/analytics_dashboard.html` — Table tab button, pane, loadTable(), _updateTable, col state JS/CSS, session detail modal moved here
  - `survey/templates/editor/partials/analytics_geo_map.html` — remove session detail modal (moved to dashboard)

## Out of Scope

- Inline editing of answers (backlog #47)
- Validation status column (backlog #40)
- Bulk operations toolbar (backlog #42)
- Answer-level linting markers in cells (backlog #44)
- Mobile responsive table layout
