## Why

On 2026-09-22 an editor got HTTP 500 from `analytics_answer_edit` (PostHog error tracking,
`Answer.MultipleObjectsReturned` at `analytics_views.py:384`). Question 6981 is a `point`
question; every affected session holds three root answers for it — one per placed point. The
legacy Responses table makes EVERY question cell editable on double-click, geo and file columns
included, and the view runs `Answer.objects.get_or_create(session, question, parent_answer_id__isnull=True)`
before it looks at the question type. A geo question with more than one feature therefore 500s;
with zero features the same call silently inserts an empty `Answer` row before returning 400.

A production check on 2026-09-28 found duplicate root answers only on `point` (1091 session/question
pairs), `line` (79) and `polygon` (79) — i.e. legitimate multi-feature answers. No text/number/choice
question has duplicates, so the section-POST delete-then-insert is not implicated.

## What Changes

- One list of inline-editable answer types, `EDITABLE_ANSWER_TYPES` in `survey/analytics.py`,
  used by the session detail rows, the Responses table columns and the edit endpoint.
- `analytics_answer_edit` rejects a non-editable question type with 400 BEFORE touching the
  database, so it never creates a stray row and never hits the multi-row case.
- For editable types it updates the earliest existing root answer (`filter().order_by('id').first()`)
  or creates one, so an unexpected duplicate can never turn an edit into a 500.
- The legacy Responses table (`analytics_table.html`) offers double-click editing only on columns
  whose type is editable.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `analytics-data-workspace`: inline answer editing is limited to single-value types and never
  fails on multi-feature answers.

## Impact

- `survey/analytics.py`, `survey/analytics_views.py`, `survey/templates/editor/partials/analytics_table.html`
- `survey/tests.py` — regression tests.
- No migrations, no settings, no kill switch. `thumbs` was accepted by the endpoint but offered by
  no UI; it drops out of the endpoint with the shared list.
