## 1. Backend

- [x] 1.1 Add `analytics_bulk_set_status` view: accepts JSON `{session_ids, status}`, iterates and calls `SessionValidationService.set_status()` in `transaction.atomic()`
- [x] 1.2 Add `analytics_bulk_trash` view: accepts JSON `{session_ids}`, iterates and calls `SessionValidationService.trash()`
- [x] 1.3 Add `analytics_bulk_restore` view: accepts JSON `{session_ids}`, iterates and calls `SessionValidationService.restore()`
- [x] 1.4 Add `analytics_bulk_hard_delete` view: accepts JSON `{session_ids}`, iterates and calls `SessionValidationService.hard_delete()`
- [x] 1.5 Add 4 URL patterns to `survey/urls.py`

## 2. Template & JS

- [x] 2.1 Add bulk toolbar HTML in `analytics_table.html`: selected count, Change Status dropdown, Trash/Restore/Hard Delete buttons
- [x] 2.2 Wrap existing toolbar in `#toolbar-normal` div
- [x] 2.3 JS: `getSelectedIds()` function, `updateBulkToolbar()` on checkbox change
- [x] 2.4 JS: bulk action functions in `analytics_dashboard.html`: `bulkSetStatus()`, `bulkTrash()`, `bulkRestore()`, `bulkHardDelete()`
- [x] 2.5 Wire select-all checkbox to trigger `updateBulkToolbar()`
- [x] 2.6 Confirm dialogs for destructive bulk actions

## 3. Tests

- [x] 3.1 Test `analytics_bulk_set_status` sets status on multiple sessions
- [x] 3.2 Test `analytics_bulk_trash` trashes multiple sessions
- [x] 3.3 Test `analytics_bulk_restore` restores multiple trashed sessions
- [x] 3.4 Test `analytics_bulk_hard_delete` permanently deletes trashed sessions
- [x] 3.5 Test viewer role cannot call bulk endpoints (403)
- [x] 3.6 Test invalid session IDs are ignored (no crash)
