# Survey answers are never validated server-side

**Type**: bug
**Priority**: high
**Area**: backend
**Created**: 2026-08-05

## Description

The section POST handler builds the answer form with `initial=request.POST` rather than binding it
to the data (`survey/views.py:812`):

```python
form = SurveySectionAnswerForm(initial=request.POST, section=section, ...)
```

An unbound form is never validated. `is_valid()` is never called and `form.errors` is never read;
the handler proceeds straight to writing answers. So for **every question type**:

- `required` is not enforced. A respondent who submits an empty section is taken to the next one,
  and on the last section to the thanks page, as though they had answered.
- Field-level validation does not run — no type checking, no min/max, no choice-membership check.
- A crafted request can put values into `Answer` that the form would have rejected. An empty string
  posted for a `number` or `range` question reaches `float(result[0])` and raises, returning a 500
  (`views.py:875`).

Client-side `required` attributes are the only thing enforcing this today, so anything that bypasses
the browser form — a script, a replayed request, a mobile browser that handles `required` loosely —
writes unchecked data.

## Notes

- Found 2026-08-05 while writing tests for change `range-scale-display`. A spec scenario asserted
  that a required range question rejects an empty submission; it does not, and neither does any
  other type. The scenario was rewritten to assert what the platform actually guarantees rather than
  quietly dropped.
- This is the general case of a symptom already recorded from the web-concurrency work: "geo-question
  `required` not enforced server-side (empty submit → thanks)". That note framed it as a geo issue.
  It is not — it is every question type, and the cause is one line.
- Fixing it is not a one-liner despite the cause being one, because unknown numbers of live surveys
  currently accept partial responses. Turning validation on will start rejecting submissions that
  are being accepted today, so it needs a decision about existing in-flight surveys and probably a
  look at how many stored sessions would have failed validation.
- Sequence the work: bind the form and surface errors without enforcing `required` first, measure how
  many submissions would fail, then enforce. Sequencing it the other way risks silently dropping
  respondents mid-consultation, which is worse than the current gap.
- The 500 on an empty numeric value is separable and worth fixing immediately regardless — guard the
  `float()` conversions in the save path.
