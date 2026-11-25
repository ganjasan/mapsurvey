## 1. Implementation

- [x] 1.1 `map_position_picker.js`: `lock` option — handlers off, overlay with "Change position", "Done" button, re-lock on outside press and on leaving the viewport; `lock()` / `unlock()` on the returned object; `detach()` undoes it
- [x] 1.2 `survey_settings.html`, `survey_settings_panel.html`: pass `lock: true` and the two labels; section modal untouched
- [x] 1.3 `editor_base.html`: styles for the lock overlay and buttons (tokens only)
- [x] 1.4 "Change position" in every catalog
- [x] 1.5 Tests (GIVEN/WHEN/THEN) in `survey/tests/test_survey_editor.py`
- [x] 1.6 Changelog entry; `.claude/architecture/creator-ui.md`

## 2. Verification

- [x] 2.1 Browser check: wheel and drag over the locked map move nothing and post nothing; unlock → drag saves; outside click re-locks
- [x] 2.2 `./run_tests.sh survey.tests.test_survey_editor survey.tests.test_ui_internationalization` (`ReportsCatalogTest` fails on main too: untranslated `fi` report strings, not this change)
- [x] 2.3 `openspec validate map-picker-lock --strict`
