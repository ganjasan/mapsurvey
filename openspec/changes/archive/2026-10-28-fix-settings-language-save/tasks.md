## 1. Fix

- [x] 1.1 `language_picker.html`: dispatch `change` on the hidden input after an add or a remove, not on initial render
- [x] 1.2 `survey_settings_panel.html`: exclude `#lang-search` from `PanelAutosave`

## 2. Verify

- [x] 2.1 Test pinning the picker wiring and the exclusion; panel POST with `available_languages` saves
- [x] 2.2 Browser on the dev server: click Spanish; type + click French; remove a tag — each survives a reload
