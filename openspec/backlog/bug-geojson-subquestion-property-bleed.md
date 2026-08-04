# GeoJSON export: sub-question property inherits the previous sub-question's value

**Type**: bug
**Priority**: **very high**
**Area**: backend
**Created**: 2026-08-04

## Description

In the GeoJSON branch of `download_data`, the accumulator `result` is initialised once *before*
the loop over sub-questions (`survey/views.py:1098`) instead of once per sub-question. Inside the
loop `result` is only reassigned when the sub-question actually has an answer of a handled input
type. So a sub-question that was left blank — or whose type is not in the handled set
(`datetime`, geo types, `image`, `html`) — is written out carrying the value of whichever
sub-question was processed before it:

```python
result = ""                       # <- outside the loop
for key in subanswers:
    if input_type in ("text", "text_line"):
        if subanswers[key]:       # <- no else branch
            result = ...
    ...
    properties[key.name] = result # <- stale value when nothing matched
```

This is silent data corruption, not a crash: the exported GeoJSON is well-formed and looks
plausible, but attribute values are attached to the wrong attribute. Anyone analysing the export
has no way to tell which values are real. Severity is driven by that silence — the numbers a
customer reports to their stakeholders may be wrong.

Affects every survey whose geo questions carry sub-questions, which is the documented way to model
attributes of a mapped object.

## Notes

- Found 2026-08-04 while investigating Manuel Frost's export complaint; not what he reported, and
  he has not noticed it. His RuE noise-plan surveys use geo questions with sub-questions, so his
  exports are likely affected.
- Second defect in the same block: `answer` is rebound to a sub-answer inside the loop
  (`views.py:1103` and friends), shadowing the geo answer being exported. Currently benign because
  `subAnswers()` is evaluated before the rebind and the session is the same object, but it makes
  `properties["session"]` at `views.py:1125` read from the wrong row and will bite on the next
  edit to this function. Fix both together.
- Related: [datetime answers missing from CSV export](bug-datetime-missing-from-csv-export.md) —
  same function, same cause shape, fixed together.
- **2026-08-04 — FIXED** in change `export-data-integrity`, branch `fix/export-data-integrity`.
  Both duplicated `elif` chains were replaced by a single `_answer_cell(question, answers)`, so the
  accumulator that leaked no longer exists; the `answer` rebinding went with it. Covered by
  `ExportValueCorrectnessTest` in `survey/tests.py`.
- Mechanism, confirmed while fixing: sub-answers are written only for keys present in the submitted
  feature's `properties` (`views.py:841`), so a sub-question the respondent skipped has **no
  `Answer` row at all**. That is the ordinary path, not an edge case — the bug fires whenever a
  respondent leaves an attribute blank.
- Correction to an earlier note in this file: `download_data` was described as untested. It was
  not — it had tests for row counts, the version filter and metadata columns. The gap was
  value-level: nothing asserted that an answer reached the right column, and nothing exercised
  sub-questions. That gap is now closed.
