## 1. Constant

- [x] 1.1 Add `CHOICE_TYPES = ("choice", "multichoice", "range", "rating", "ranking")` to
      `survey/question_types.py`, next to `GEO_TYPES`.

## 2. Respondent POST dispatch (`survey/views.py`)

- [x] 2.1 Top-level loop: branch on `input_type` (geo / ranking / choice-multichoice-rating /
      number-range / text-text_line-datetime); drop the `if not question.choices` gate.
- [x] 2.2 Sub-question properties loop: same dispatch by `sub_question.input_type`.
- [x] 2.3 datetime (both levels) stores to `text`; range gains number's empty-value guard.

## 3. Editor write paths (`survey/editor_views.py`)

- [x] 3.1 `editor_question_create`, `editor_question_edit`, `editor_subquestion_create`: apply
      posted `choices_json` only when `input_type in CHOICE_TYPES`; otherwise force
      `choices = None`.

## 4. Import (`survey/serialization.py`)

- [x] 4.1 After resolving choices, null them when `input_type not in CHOICE_TYPES`.

## 5. Migration

- [x] 5.1 `0060`: data migration clearing `choices` on questions of non-choice types; reverse
      is a no-op.

## 6. Tests

- [x] 6.1 Poisoned point question (choices non-empty) → POST with GeoJSON saves geometry, 200/302
      (adorion's case, was 500).
- [x] 6.2 Poisoned text sub-question → value lands in `text`.
- [x] 6.3 datetime top-level and sub-question persist to `text`; prepopulation reads it back.
- [x] 6.4 Editor type switch choice→point with stale `choices_json` posted → `choices is None`
      (create, edit, subquestion paths).
- [x] 6.5 Import of ZIP with choices on a point question → `choices is None`.
- [x] 6.6 Migration clears geo choices, keeps choice/ranking lists.
- [x] 6.7 Full survey suite; compare to baseline. 1515 tests, OK (skipped=1) — baseline 1505 + 10 new.
