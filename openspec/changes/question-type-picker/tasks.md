# Tasks — question type picker rework

## 1. Metadata

- [x] 1.1 Create `survey/question_types.py`: `PICKER_GROUPS` (Questions / Map questions / Display
      blocks) and per-type metadata — icon class, one-line hint, optional `display_label`
      (`html` → "Formatted Text"). Values and order taken from the approved mockup.
- [x] 1.2 Parity test: metadata keys == `INPUT_TYPE_CHOICES` keys, every type belongs to exactly
      one group (GIVEN/WHEN/THEN docstring).

## 2. Preview machinery (server)

- [x] 2.1 `survey/forms.py`: make `_get_form_from_input_type` a classmethod (self is unused);
      add `single_question_form(question, language=None)` building a one-field form for a
      possibly-unsaved question (resolve display style, set widget attrs — mirror `__init__`).
- [x] 2.2 Refactor `editor_question_preview` onto the factory; behaviour unchanged (existing
      display_style override preserved).
- [x] 2.3 New `editor_question_preview_live(request, survey_uuid, section_id)` (POST): build an
      unsaved `Question` from `input_type`, `name`, `choices_json`, `display_style`, `color`,
      `icon_class`; defensive `choices_json` parsing; render `question_preview_frame.html`;
      `viewer` permission + same-origin frame header. Route in `urls.py`.
- [x] 2.4 Tests: live preview returns the real widget for rating (radios from posted choices),
      range slider bounds from choices, geo draw button with posted colour/icon, display block
      renders content, invalid `choices_json` falls back instead of 500, permission enforced,
      unknown input_type rejected cleanly, nothing is saved.

## 3. Modal layout

- [x] 3.1 Widen the dialog to 1100px ≥1200px viewport. Done without touching `survey_detail.html`:
      `#questionModal .modal-dialog` from the partial's style block outranks `.modal-lg`.
- [x] 3.2 `question_form_modal.html`: restructure body into form column + preview pane (both
      create and edit); move the existing edit-mode iframe into the pane.

## 4. Picker UI

- [x] 4.1 Card grid partial rendered from metadata × the form field's actual choices (sub-question
      restrictions respected); native select hidden but present; card click sets select value +
      dispatches `change`; selected card highlighted; hint line under the grid.
- [x] 4.2 `question_type_examples.html`: canned example snippet per type (from mockup); hovering a
      card shows it in the preview column under "Respondent sees" (revised from a floating flyout
      during review); suppressed on touch, absent below `lg` with the whole column.
- [x] 4.3 Styles: kept inline in the modal partial's `<style>` block — the editor's existing idiom
      (the partial already styles `#display-style-fields` inline); no static asset touched, so no
      collectstatic needed. Example snippets are hidden `<div>`s, not `<template>`s: htmx delivers
      swaps wrapped in a template, and nested templates broke fragment parsing (the partial's
      script never ran).

## 5. Field visibility (#111)

- [x] 5.1 `toggleTypeScopedFields`: Color + Icon geo-only, Image only for `image`, Required hidden
      for `image`/`html`; wired into the same change listener chain.
- [x] 5.2 Confirm hidden text/color inputs still submit (no data clearing on save of untouched
      questions); note the `required` unchecked exception in code where it happens.

## 6. Live preview (client)

- [x] 6.1 Debounced (~400ms) listener over name/text, choices editor, display style, color, icon,
      type change → POST to the live endpoint → `iframe.srcdoc`; stale responses discarded.
- [x] 6.2 New question: pane live-renders the draft immediately on open (better than the planned
      canned placeholder — the endpoint is there anyway); edit mode: starts from the existing
      saved-state URL, live render takes over on first change. `QuestionForm` now pre-selects
      `text` for new questions so cards, select and preview agree from the first render (the
      select used to start on Django's "---------" empty option).

## 7. Verify

- [x] 7.1 `./run_tests.sh survey` green (baseline first, then after).
- [x] 7.2 Walk the dialog in the running editor: create flow (all groups, flyout, live pane),
      edit flow (existing question loads, live updates), sub-question flow (restricted types),
      screenshots for the PR.
- [x] 7.3 Update backlog: #112 promoted → this change; #111 closed by §5; INDEX rows; move the
      mockup file here (done at change creation).
