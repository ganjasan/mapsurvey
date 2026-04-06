## Why

Session-level issues (#43) flag sessions as empty/incomplete/missing-required, but researchers also need per-answer quality checks. A polygon with self-intersecting geometry is invalid GIS data; a required question with no answer means corrupted submission. These errors should be visible directly in the table cell where the problem is.

## What Changes

- New `compute_answer_lints()` method computing per-answer errors via bulk queries
- Two rules: self-intersection (polygon), empty required (required question with no answer in visited section)
- Error icon + cell highlight in the attribute table for linted answers
- `has_errors` option in the Issues dropdown filter to show only sessions with answer-level errors

## Capabilities

### New Capabilities
- `answer-linting-errors`: Per-answer error detection with visual indicators in table cells

### Modified Capabilities
- `get_table_page`: Lint map merged into row data for template rendering
- `analytics_table.html`: Cell-level error icons and highlighting
- Issues filter: new `has_errors` option

## Impact

- `survey/analytics.py` — `compute_answer_lints()` method, integration into `get_table_page()`
- `survey/templates/editor/partials/analytics_table.html` — cell error rendering + filter option
- `survey/tests.py` — tests for both lint rules
