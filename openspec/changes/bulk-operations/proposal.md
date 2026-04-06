## Why

After #40 (Session Validation Status), researchers can change status and trash sessions one at a time. With 500+ responses, doing this individually is impractical. The checkbox UI is already in place (select all + per-row checkboxes from #40) but has no actions wired to it.

## What Changes

- Sticky bulk-action toolbar replaces normal table toolbar when rows are selected
- Shows selected count + actions: Change status (dropdown), Trash, Restore, Hard delete
- In trash mode: Restore + Hard delete + Change status available
- In normal mode: Change status + Trash available
- 4 new bulk endpoints accepting list of session IDs
- JS tracks selection state and wires toolbar actions

## Capabilities

### New Capabilities
- `bulk-operations-toolbar`: Contextual toolbar appearing on row selection with bulk status change, trash, restore, hard delete

### Modified Capabilities
- `analytics_table`: Toolbar switches between normal/bulk mode based on selection

## Impact

- `survey/analytics_views.py` — 4 new bulk POST endpoints
- `survey/urls.py` — 4 new URL patterns
- `survey/templates/editor/partials/analytics_table.html` — bulk toolbar HTML + JS
- `survey/templates/editor/analytics_dashboard.html` — bulk action JS functions
- `survey/tests.py` — tests for bulk endpoints
