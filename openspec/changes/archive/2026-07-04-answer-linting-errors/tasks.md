## 1. Service Layer

- [x] 1.1 Add `compute_answer_lints(session_pks, answer_qs)` method to `SurveyAnalyticsService`
- [x] 1.2 Rule: self-intersection — check `polygon.valid` for polygon answers during cell pivot
- [x] 1.3 Rule: empty required — required questions without answer in visited sections
- [x] 1.4 Integrate into `get_table_page()`: compute lints, add `lints` key to row dicts, pass `lint_map` for template
- [x] 1.5 Add `has_errors` to issues_filter logic

## 2. Templates

- [x] 2.1 Render error icon + cell highlight for linted cells in `analytics_table.html`
- [x] 2.2 Add `has_errors` option to issues filter dropdown
- [x] 2.3 CSS for error cell highlighting (inline styles)

## 3. Tests

- [x] 3.1 Test self-intersection polygon detected
- [x] 3.2 Test valid polygon has no lint
- [x] 3.3 Test empty required answer detected
- [x] 3.4 Test `has_errors` filter returns only sessions with lints
- [x] 3.5 Test `get_table_page` includes lint data in rows
