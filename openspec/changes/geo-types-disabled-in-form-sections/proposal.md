## Why

In a section with `layout = "form"` the question type picker drops the whole "Map questions"
group, and nothing says why. A new creator (issue #323, session replay 2026-10-14) switched the
first section of a map-shaped survey to Form, opened "New Question" there and found no map types
at all.

## What Changes

- In a Form section the picker keeps the "Map questions" group, every card disabled (not
  clickable, not focusable, no hover example), with one line under the group: "This section has
  no map. Switch its Layout to Map to add a map question."
- The server keeps rejecting a map `input_type` in a Form section — only the display changes.
- The Layout help text in the section settings adds that a Form section cannot hold map questions.

## Capabilities

### Modified Capabilities
- `survey-editor`: "Question type picker respects the section layout" — disabled with a reason
  instead of absent.

## Impact

`survey/editor_forms.py` (QuestionForm marks the removed types as `unavailable_types`),
`survey/question_types.py::picker_groups_for`, `question_utils.question_type_picker`,
`editor/partials/question_type_picker.html`, picker CSS in `question_form_modal.html`,
`editor/partials/section_detail_form.html`. No model or migration.
