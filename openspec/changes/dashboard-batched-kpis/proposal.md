## Why

The editor dashboard (`/editor/`) is the slowest creator page on production — 450–900 ms of
server time on 2026-10-19, against 50–200 ms for Build, Share or Public results — and it grows
with every survey in the workspace and every answer they hold (#362). The view builds the card
list with grouped queries, then calls `SurveyAnalyticsService(survey).get_overview()` once per
survey to get two numbers, *completed* and *completion %*. Each call runs ~10–12 queries, and
`compute_session_issues()` inside it loads every top-level answer pair of the survey into Python
to produce `flagged_count`, which the dashboard never shows.

## What Changes

- New `analytics.family_completion_counts(surveys)`: `{canonical_id: (total, completed)}` for a
  list of canonical surveys in a constant number of queries — version families resolved by
  `canonical_survey`, last section of every version from one section query, totals and completed
  counts grouped by family. "Completed" keeps its one definition: a non-deleted session that
  answered a question of its version's last section (`completed_session_filter`).
- The last-section walk is split so a list of already-loaded sections can be ordered without a
  query per survey; `_get_last_section` keeps its behaviour.
- The dashboard view drops the per-survey `SurveyAnalyticsService` loop and reads the card
  numbers from the batched counts. The numbers shown do not change.
- Tests: the card numbers equal `get_overview()` for single- and multi-version families (deleted
  sessions, draft-copy sessions, empty surveys); the dashboard's query count is the same for 2
  and for 8 surveys.

## Capabilities

### New Capabilities

### Modified Capabilities
- `survey-editor`: adds a requirement that the dashboard card statistics come from family-wide
  counts whose cost does not grow per survey, and agree with the Responses overview.

## Impact

- `survey/analytics.py` — new batched helper, section-ordering helper split out.
- `survey/views.py::editor` — per-survey loop replaced.
- `survey/tests.py` — equivalence and query-count tests.
- No migrations, no template, URL or setting changes. `SurveyAnalyticsService.get_overview()`
  is untouched; the Responses page keeps using it.
