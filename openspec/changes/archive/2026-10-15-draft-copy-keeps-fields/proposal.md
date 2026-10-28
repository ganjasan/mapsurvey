## Why

Publishing "Unpublished changes" on a live survey silently strips structure the creator never
touched (#329, reproduced on production 2026-10-14): both conditional questions lost their
`visibility_rule` and are now shown to everyone, the form section came back as a `map` section,
and the "Start the tour" button label went back to "Next". The draft copy is where it is lost —
`versioning.clone_survey_for_draft` copies `SurveySection` field by field and was never taught
`layout`, `next_label`, `hidden_layers` and `visibility_rule` (nor `next_label` on the section
translations), and `cloning.clone_question` keeps a question's rule only when the target is the
same `SurveyHeader`, which a draft is not. Publish then copies the draft back over the live
structure, so every creator who uses the draft path on a survey with conditional logic, form
sections or custom button labels loses them with no warning.

## What Changes

- The draft copy keeps question and section visibility rules (codes are stable across the copy, so
  the controller still resolves), `layout`, `next_label`, `hidden_layers` (layers belong to the
  canonical survey, so the ids stay valid) and the translations' `next_label`.
- Sections and their translations are copied through ONE helper in `survey/cloning.py`, used by
  `clone_survey_for_draft` and `clone_section`, that takes every concrete non-relational field from
  the model rather than a hand-written list — a new `SurveySection` field cannot be forgotten in
  one of the two paths. `clone_question` takes its plain fields the same way.
- A guard test compares every concrete field of `SurveySection`, `SurveySectionTranslation`,
  `Question` and `QuestionTranslation` between a live survey and its draft (ids and FKs excluded)
  and fails when a field is not copied; a round-trip test (rules + form section + button labels →
  draft → publish) asserts all of it survives.
- A report (management command, read-only) lists the surveys published from a draft whose archived
  version carries rules, a form layout, hidden layers or a button label that the canonical lost, so
  the owner can decide what to restore. Nothing is restored automatically.

## Capabilities

### New Capabilities

### Modified Capabilities
- `draft-copy-lifecycle`: adds the requirement that a draft copy is structurally complete — every
  field of a section, a question and their translations survives the copy and the publish.
- `conditional-visibility`: the "Duplication carries the rule within a survey" requirement gains
  the draft copy as an in-survey case.

## Impact

`survey/cloning.py`, `survey/versioning.py`, one management command, tests. No model or migration
change. The ZIP path (`serialization.py`) already carries all of these fields and is untouched.
