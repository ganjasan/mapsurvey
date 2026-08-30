# Tasks: fix-editor-500s

## 1. Section POST survives a mistyped controller value

- [x] 1.1 `survey/views.py`: replace the bare `[int(v) for v in ...]` in the submitted-state visibility pre-pass with a tolerant parse that skips non-integer values
- [x] 1.2 Comment it with the cause (creator switches question type while respondents hold the page) so the next reader does not "simplify" the guard away — the storage branch below carries the same note

## 2. Structure export works on remote storage

- [x] 2.1 `survey/serialization.py`: `collect_structure_images()` returns `(archive_path, bytes)` read via `question.image.open()`; skip and report an image the backend cannot open
- [x] 2.2 Update the caller in `export_survey_zip` to `zf.writestr(archive_path, data)`
- [x] 2.3 Drop the now-stale `.path`-on-S3 warning from `collect_layer_files`'s docstring

## 3. Nav dropdowns on Share and Settings

- [x] 3.1 `survey_share.html`: include `editor/partials/_lifecycle_scripts.html`
- [x] 3.2 `survey_settings.html`: same
- [x] 3.3 Check every other template including `_survey_nav_tabs.html` for the same omission

## 4. Tests

- [x] 4.1 Section POST with GeoJSON under a `choice` question stores the other answers and returns no 500
- [x] 4.2 Section POST with ordinary choice values still drives conditional visibility unchanged
- [x] 4.3 Structure export of a survey with a question image succeeds and the archive holds the bytes; a storage backend that raises on open yields a warning, not an exception
- [x] 4.4 Share and Settings pages render `navMenuToggle` (assert on markup, per `lesson_test_client_misses_html5_validation`)

## 5. Verification

- [x] 5.1 `./run_tests.sh survey` — compare against the 1663-test / OK baseline
- [ ] 5.2 After merge + deploy, mark PostHog issues `01a035f7`, `01a04ddb`, `01a02d79` resolved
