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
- Fix: initialise `result = ""` at the top of each sub-question iteration, and rename the inner
  variable. Add a regression test covering a geo answer whose sub-questions are partially filled.
- Related: [Number field blank in CSV export](bug-number-field-blank-in-csv-export.md) (#23) and
  [datetime answers missing from CSV export](bug-datetime-missing-from-csv-export.md) — all three
  live in the same untested export path, which argues for one change that covers the whole
  function rather than three point fixes.
