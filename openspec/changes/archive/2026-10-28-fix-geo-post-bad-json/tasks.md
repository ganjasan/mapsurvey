## 1. Server hardening

- [x] 1.1 In `survey_section` POST, wrap the per-chunk decode → `GEOSGeometry` step in a narrow
      `try/except (ValueError, KeyError, TypeError, GEOSException)`; on failure log a warning with the
      question code and chunk prefix and `continue`.
- [x] 1.2 Regression tests (GIVEN/WHEN/THEN) for the three spec scenarios: comma-prefixed chunk,
      garbage-then-valid, non-Feature JSON.

## 2. Client hardening

- [x] 2.1 In `base_survey_template.html` `htmx:configRequest`, coerce an array parameter value to a
      string (`join('')`) before appending feature GeoJSON.

## 3. Verification

- [x] 3.1 Run the survey test suite in the worktree; delta against baseline.
