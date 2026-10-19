## 1. Batched counts

- [x] 1.1 Split section ordering out of `_get_ordered_sections` into `_order_sections(sections)` so a pre-loaded list can be ordered without a query
- [x] 1.2 Add `analytics.family_completion_counts(surveys)` → `{canonical_id: (total, completed)}`: family headers in one query, sections in one, totals and completed counts grouped by family

## 2. Dashboard

- [x] 2.1 Replace the per-survey `SurveyAnalyticsService(...).get_overview()` loop in `views.editor` with the batched counts; rate = `round(completed / total * 100)` or 0

## 3. Tests

- [x] 3.1 Equivalence: card numbers equal `get_overview()` for a multi-version family with deleted and draft-copy sessions, and for a survey without sessions
- [x] 3.2 Query count: dashboard with 2 and with 8 surveys runs the same number of queries
- [x] 3.3 Run the dashboard and analytics test classes; then the full `survey` suite once
