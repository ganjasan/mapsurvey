# AI drafts mark the "Other, please specify" option

**Type**: feature
**Priority**: low
**Area**: ai
**Created**: 2026-09-16

## Description

The native write-in option (change `other-option-write-in`) is a flag on one choice of a
`choice`/`multichoice` question. AI-generated drafts cannot set it: `survey/ai/schema.py::_choice`
declares `additionalProperties: False` with only `code` and `name`, so the model physically
cannot emit `other`. Creators add the flag by hand in the editor after generation.

## Notes

- Cost: one schema property (`"other": {"type": "boolean"}`, listed in `required` because the
  strict structured output treats optional keys poorly, so every option carries `other: false`),
  a prompt line ("at most one option per question may be the write-in"), and a strip of
  `other: false` in `survey/ai/materialize.py::_choices`. `_guard_choice_codes` already clamps
  to one flag on save.
- Worth doing once a generated survey with an "Other (please specify)" option is seen in the
  wild; AI is the main publication path, so the gap will show.
