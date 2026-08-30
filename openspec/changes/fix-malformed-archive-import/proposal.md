# Proposal: fix-malformed-archive-import

## Why

Importing a ZIP whose `survey.json` carries an explicit `null` where text belongs returns a 500.
PostHog issue [`01a02d72`](https://eu.posthog.com/project/248938/error_tracking/01a02d72-1ab8-74a2-ad84-1352809d3834),
2026-08-23, on `/editor/import/`. The stack gives the line:

```
import_survey → import_survey_from_zip → import_structure_from_archive → create_survey_header
  → TypeError: 'NoneType' object is not subscriptable
```

which at that revision was:

```python
redirect_url=survey_data.get("redirect_url", "#")[:250],
```

`.get(key, default)` reads as safe and is not: the default fires only when the key is **absent**. A
`survey.json` containing `"redirect_url": null` hands back `None`, and the slice raises. The same
shape sits on `section.code` and `question.color`, and the bare-index reads (`survey_data["name"]`,
`section_data["name"]`, `question_data["code"]`) turn a missing key into a `KeyError` — also a 500.

An archive is content from outside this installation. It can be hand-edited, truncated, produced by
an older export, or written by a different tool, and the creator who uploads one is not doing
anything wrong enough to deserve a stack trace. The view already knows how to report a bad archive —
it catches `ImportError` and renders the message — so the only thing missing is that these failures
reach it as `ImportError`.

## What Changes

- **`_archive_text(data, key, default, limit)`** — reads a text field treating an explicit `null`
  exactly like a missing key, and slices safely. Applied to `redirect_url`, `section.title`,
  `section.code`, `question.color`, `question.icon_class`.
- **`_required_text(data, key, what, limit)`** — for the three fields the import cannot invent
  (`survey.name`, `section.name`, `question.code`), raises `ImportError` naming the element instead
  of letting a `KeyError` escape.
- **A catch-all around the import**: `TypeError`, `KeyError`, `IndexError`, `AttributeError` and
  `ValueError` become an `ImportError` carrying the original type and message. This is the part that
  lasts. An archive's fields cannot all be enumerated — the next hand-edited file will null out
  something this PR did not touch — so the default has to be "a message", not "a 500".
  `logger.exception` keeps the original traceback in the request log, so a genuine bug hiding behind
  a shape error still leaves a trail.

## Also: `SurveySection.DoesNotExist` needs no work

The other server error in this batch, [`01a036e2`](https://eu.posthog.com/project/248938/error_tracking/01a036e2-a32b-7942-9f9c-4fdb14aa4307),
**is already fixed.** Its stack points at `survey/views.py`, frame `survey_section`, where the code
then read:

```python
section = SurveySection.objects.get(Q(survey_header=session_survey) & Q(name=section_name))
```

Commit `f94e9cc` (2026-08-25 10:43, seven hours after the single recorded event) replaced it with
`.filter(...).first()` and a redirect to the survey entry point when the name resolves to nothing.
No code is needed; the issue is marked resolved.

## Capabilities

### Modified Capabilities

- `survey-serialization`: a malformed archive is rejected with a readable message rather than a 500,
  and an explicit `null` is read as an absent field.

## Impact

- **Code**: `survey/serialization.py`, tests in `survey/tests.py`.
- **No migrations, no settings, no URL changes.**
- **Well-formed archives are unaffected** — a baseline test asserts the ordinary import still works,
  so the null cases cannot pass for the wrong reason.
- **Behaviour change**: an import that used to 500 now redirects with an error message naming the
  problem. Nothing that previously imported stops importing.
