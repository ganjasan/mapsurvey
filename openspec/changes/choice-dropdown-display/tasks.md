# Tasks: choice-dropdown-display

## 1. Respondent rendering

- [x] 1.1 Add a `ChoiceDropdownWidget` in `survey/forms.py`: search `<input>`, hidden
      `<select>` carrying the real value, filterable option list; new widget template
      with minimal vanilla JS (substring filter, click/Enter select, listbox ARIA roles).
- [x] 1.2 Extend `resolve_display_style` to a per-input-type map (`rating` keeps its
      styles; `choice` gains `dropdown`) and branch `_get_form_from_input_type` for
      `choice` + `dropdown`.
- [x] 1.3 Tests (GIVEN/WHEN/THEN): dropdown markup rendered for opted-in question; radio
      markup unchanged for default; submitted code saves identically; required error;
      `dropdown` on non-choice type ignored.

## 2. Editor

- [x] 2.1 Show the display-style selector for `choice` questions in
      `editor/partials/question_form_modal.html` (List / Dropdown with search) —
      minimal, localized edit; the file is also touched by `formatted-text-wysiwyg`.
- [x] 2.2 Server-side save in `editor_views.py`: accept `dropdown` only for
      `input_type == 'choice'`, normalize otherwise.
- [x] 2.3 Tests: save persists `dropdown` on choice; `dropdown` on text normalizes to
      `default`; template guard test right after the modal edit.

## 3. Serialization

- [x] 3.1 Make the `_create_question` display-style whitelist type-aware; accept
      `dropdown` for choice questions.
- [x] 3.2 Tests: round-trip keeps `dropdown` on choice; falls back to `default` on
      non-choice.

## 4. Ship & apply to Olney

- [ ] 4.1 Full test run via `./run_tests.sh survey`; PR referencing this change.
- [ ] 4.2 After deploy: `UPDATE survey_question SET display_style='dropdown' WHERE id=4190;`
      and verify the 35-zone question on the live test link (desktop + phone).
