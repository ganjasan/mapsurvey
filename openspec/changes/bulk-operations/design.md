## Context

Checkboxes and select-all already exist in `analytics_table.html` from #40. `SessionValidationService` handles individual mutations. The bulk toolbar needs to: (1) track selected session IDs, (2) show/hide contextual toolbar, (3) POST selected IDs to bulk endpoints, (4) reload the table.

## Goals / Non-Goals

**Goals:**
- Bulk change status, trash, restore, hard delete
- Sticky toolbar replacing normal toolbar when selection is active
- Works in both normal and trash mode
- Confirm dialog for destructive bulk actions (trash, hard delete)

**Non-Goals:**
- Batch edit answer values (deferred to #47 inline editing)
- Batch add tags (deferred to #48 tags & notes)

## Decisions

### 1. Bulk endpoints accept JSON body with session_ids array

POST body: `{"session_ids": [1, 2, 3], "status": "approved"}` (for status change).
Using JSON instead of form-encoded because arrays are cleaner. Views parse `json.loads(request.body)`.

### 2. Toolbar is part of `analytics_table.html` partial, toggled by JS

Two `<div>` elements in the toolbar area: `.attr-table-toolbar-normal` (existing) and `.attr-table-toolbar-bulk` (new). JS toggles visibility based on `getSelectedIds().length > 0`. The toggle runs on every checkbox `change` event.

### 3. Selection state is purely client-side

Selected IDs are read from checked `.row-select-cb` checkboxes at action time. No server round-trip to maintain selection. Selection is lost on table reload (after bulk action completes) — this is intentional and matches KoBoToolbox behavior.

### 4. Reuse SessionValidationService for each session in bulk

Bulk endpoints iterate over session IDs and call `SessionValidationService` methods in a loop inside `transaction.atomic()`. No new bulk methods on the service — keeps the single-session logic as the source of truth.
