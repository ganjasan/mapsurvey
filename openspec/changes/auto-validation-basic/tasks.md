## 1. Service Layer

- [x] 1.1 Add `compute_session_issues(session_pks)` method to `SurveyAnalyticsService` returning `{sid: [issues_list]}`
- [x] 1.2 Rule: empty sessions (0 top-level answers)
- [x] 1.3 Rule: incomplete sessions (no answer in last section)
- [x] 1.4 Rule: missing required (required questions without answers in visited sections)
- [x] 1.5 Integrate into `get_table_page()`: call `compute_session_issues`, add `issues` key to row dicts, add "Issues" system column at index 2
- [x] 1.6 Add `issues_filter` param to `get_table_page()` for filtering by issue type
- [x] 1.7 Add `flagged_count` to `get_overview()` return dict

## 2. Views

- [x] 2.1 Parse `?issues=` param in `analytics_table` view, pass to `get_table_page()`
- [x] 2.2 Pass `flagged_count` from `get_overview()` to `analytics_dashboard` template context

## 3. Templates

- [x] 3.1 Render "Issues" column in `analytics_table.html` with color-coded badges
- [x] 3.2 Add issues filter dropdown in table toolbar
- [x] 3.3 Add `issues` hidden input to `#table-state-form`
- [x] 3.4 Add "Flagged" stat card in overview partial
- [x] 3.5 JS: `changeIssuesFilter()` function + include `issues` param in `loadTable()`

## 4. Tests

- [x] 4.1 Test empty session detection
- [x] 4.2 Test incomplete session detection
- [x] 4.3 Test missing required detection
- [x] 4.4 Test session with no issues returns empty list
- [x] 4.5 Test `get_table_page` includes issues in row dicts
- [x] 4.6 Test issues filter in `get_table_page`
- [x] 4.7 Test `get_overview` includes `flagged_count`
- [x] 4.8 Test `analytics_table` view with `?issues=empty` filters correctly
