# Proposal: choice-dropdown-display

## Why

A `choice` question always renders as a radio list — with many options it swallows the
whole section panel (live case: the Olney squirrel-count demo has a 35-zone question that
pushes every geo question below the fold on mobile). Creators need a compact rendering:
a dropdown with a search box, chosen explicitly per question.

## What Changes

- New `display_style` value `dropdown` for `choice` questions: the respondent sees a
  search input; typing filters the option list; picking an option fills the field.
  Radio rendering stays the default — no silent auto-switch for existing surveys.
- Editor: the question form offers the style ("List" / "Dropdown with search") when the
  question type is `choice`, reusing the existing display-style plumbing built for rating.
- Import/export: `dropdown` becomes a known `display_style` value that round-trips through
  `survey.json` (unknown values still fall back to `default` per the existing rule).
- After deploy: set `display_style = 'dropdown'` on the Olney zone question.

## Capabilities

### New Capabilities

- `choice-dropdown-display`: how a `choice` question with `display_style = "dropdown"`
  renders and behaves for respondents (search input, filtered list, selection, validation,
  keyboard/mobile behavior), and how the style is scoped strictly to `choice`.

### Modified Capabilities

- `survey-editor`: the question modal offers a display-style picker for `choice` questions
  (today the picker exists only for rating).
- `survey-serialization`: `dropdown` joins the known `display_style` values that survive
  export→import round-trip for choice questions.

## Impact

- `survey/forms.py` — new widget + field branch for `choice` with `dropdown` style;
  `resolve_display_style` currently whitelists rating styles only.
- Widget template + a small vanilla-JS filter (no new dependencies).
- `survey/editor_views.py`, `editor/partials/question_form_modal.html` — style picker for
  choice (careful: this modal is touched by the in-flight `formatted-text-wysiwyg` change).
- `survey/serialization.py` — `_create_question` display_style whitelist gains `dropdown`.
- `survey/models.py` — help_text only; no migration (`display_style` is an existing CharField).
- Tests in `survey/tests.py`; guard test after template edits per project convention.
