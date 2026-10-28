## Why

Since the suite runs in parallel (#458), test order inside a worker changes from run to run.
Views call `translation.activate()` and the test client does not reset it, so a test that calls
code directly (no request) reads gettext output in whatever language the previous test in that
worker left behind. `CsvTest` was fixed by hand in #458; the next run failed
`CollectorTest.test_occurrences_in_respondent_order_with_locations` on master the same way
("Página 2 · Pergunta 1 opção"). Fixing classes one by one only moves the flake.

Production is not affected: `LocaleMiddleware` activates a language on every request.

## What Changes

- The project test runner resets the active language to the default before every test, so each
  test starts from the same state whatever ran before it in the process.
- The `CsvTest` per-class override from #458 stays (harmless, documents intent).
- The REST summary's write-in grouping (`api/v1/responses.py::_write_ins`) promises to show each
  group "as first written" but read rows in no defined order; the full parallel run failed
  `test_summary_counts_choices_and_write_ins` with "Bike lane" instead of "bike lane". The query
  now orders by `pk`. This is a real (cosmetic) API bug that parallel runs made visible.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `test-suite`: every test starts with the default language active.

## Impact

`mapsurvey/test_runner.py`, `survey/test_test_runner.py`, CLAUDE.md "Testing"; one `order_by`
in `api/v1/responses.py` (summary write-ins: deterministic "first written" spelling).
