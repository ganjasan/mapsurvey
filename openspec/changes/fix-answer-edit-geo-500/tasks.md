## 1. Fix

- [x] 1.1 Add `EDITABLE_ANSWER_TYPES` to `survey/analytics.py`; use it for detail rows and add
      `editable` to question columns.
- [x] 1.2 `analytics_answer_edit`: 400 on non-editable type before any query; replace
      `get_or_create` with earliest-existing-or-create.
- [x] 1.3 `analytics_table.html`: `cell-editable` + `ondblclick` only when `col.editable`.

## 2. Tests

- [x] 2.1 Regression tests (GIVEN/WHEN/THEN) for the four spec scenarios.
- [x] 2.2 Run the analytics test classes in the worktree.
