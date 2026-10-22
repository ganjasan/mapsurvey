## Why

A language added in the Survey settings panel is never saved (#391). The panel autosaves, but the
language picker writes the hidden `available_languages` input from JavaScript, which fires no event,
so no save is scheduled. Typing in the picker's search box first is worse: blurring the box saves the
form with the OLD value, the panel says "All changes saved", and the language chosen a moment later
is never posted. A creator who wanted to add Spanish to an English survey could not, and so could not
enter any translation. Languages chosen when the survey is created, and on the Save-button settings
page, are unaffected; only "add a language later" in the panel is broken, since the panel replaced
the Save-button page on 2026-07-01.

## What Changes

- The language picker dispatches `change` on the hidden input when the creator adds or removes a
  language (never on its initial render, so opening the panel does not save).
- The picker's search box is excluded from the settings panel autosave; typing a filter is not an edit.
- A test pins the picker wiring, and the change is verified in a browser.

## Capabilities

### Modified Capabilities

- `survey-editor`: the settings panel saves a language added or removed in the picker.

## Impact

- `survey/templates/editor/partials/language_picker.html` (also used by the Save-button settings
  page, the settings modal and the create form, where the extra `change` event is harmless).
- `survey/templates/editor/partials/survey_settings_panel.html` (autosave `exclude`).
