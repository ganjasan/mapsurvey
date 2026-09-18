## 1. Branch from the right base

- [x] 1.1 `git fetch origin` and confirm `origin/master` still ends at `fafd67d` (#193); the remote moved twice during analysis, so re-read it rather than trusting a note
- [x] 1.2 Create the worktree and branch from `origin/master`, NOT local `master` — `#192` introduced `survey/assets/js/map_position_picker.js` and rewrote the three picker call sites; editing the local pre-`#192` templates would diff against code that no longer exists
- [x] 1.3 `cp .env.ports.example .env.ports`, pick an unused `PORT_OFFSET`, and record it in the registry comment

## 2. Localization: the fourth template

- [x] 2.1 Wrap the coordinate block in `survey/templates/editor/layer_editor.html` (line 234) in `{% localize off %}`, matching the comment style the three guarded siblings use
- [x] 2.2 Confirm by hand: set the language cookie to `de`, open `/editor/surveys/<uuid>/layers/<id>/edit/`, move the pointer across the map, and see no exception in the console

## 3. Localization: a guard that covers the class

- [x] 3.1 Write the source scanner over `survey/templates/**/*.html` — extract `<script>` bodies, find Django interpolations that are neither inside `{% localize off %}` nor filtered through `|unlocalize`. Model it on `ExternalScriptCorsTest` (tests.py ~37025), which already walks the tree for the same reason
- [x] 3.2 Run the scanner BEFORE asserting on it and read every hit; guard anything legitimate rather than carving out exceptions in the detector
- [x] 3.3 Replace `test_section_map_picker_has_no_localized_decimals` and `test_survey_settings_has_no_localized_decimals` with the repository-wide test; keep `test_coordinates_are_identical_in_both_locales` and `test_guard_would_catch_a_localized_decimal`
- [x] 3.4 Confirm the new test FAILS with task 2.1 reverted — the August notes record three versions that passed against broken code
- [x] 3.5 Set the language COOKIE, not `Accept-Language`, and not `translation.override`; do not reach for `ru`, which is not in `LANGUAGES`

## 4. Z-dimension import

- [x] 4.1 Add the ordinate reduction to `validate_layer_upload` in `survey/layers.py` so coordinates are truncated to `[lng, lat]` at every nesting depth, and record whether any Z was present
- [x] 4.2 Verify `objects_from_features` (`layers.py:387`) and `layer_object_views.py:113` both receive reduced features, so the ZIP import and single-object create paths inherit it without their own copy of the logic
- [x] 4.3 Surface "elevation discarded" in the import report when Z was present
- [x] 4.4 Test: a FeatureCollection with `[6.96, 50.94, 58.2]` imports and stores `POINT(6.96 50.94)`; a 2D file stores exactly what it stored before

## 5. Atomic upload and the error contract

- [x] 5.1 Wrap the create-then-populate sequence in `editor_survey_layer_create` (`survey/editor_views.py:813`) in `transaction.atomic`
- [x] 5.2 Test: when object creation raises, no `SurveyMapLayer` row survives and the per-survey count is unchanged
- [x] 5.3 Test: a refused upload returns JSON with a readable reason, never an HTML error page
- [x] 5.4 Orphan layer 87 (survey `edffa46f`, zero objects): leave it to its creator — the Reference layers card already lists it with a delete button, so there is nothing to repair in someone else's survey

## 6. Autosave lifecycle

- [x] 6.1 Add `detach()` to `survey/assets/js/map_position_picker.js` — clear the pending timer and remove listeners
- [x] 6.2 Call `detach()` when the picker's container is torn down (HTMX `htmx:beforeCleanupElement` on the settings panel, modal close for the section picker)
- [x] 6.3 Make `payload()` abandon the save when `extraFields()` cannot build a value, rather than substituting a default — a guessed `use_geolocation=0` persists a choice the creator never made
- [x] 6.4 Null-guard the three `extraFields` call sites as a second line of defence: `survey_settings_panel.html:310`, `section_map_picker.html:111`, `survey_settings.html:182`
- [x] 6.5 Test teardown and guard independently, so a silently no-op `detach()` still fails a test
- [x] 6.6 Confirm a settled move still saves and the indicator still reports success

## 7. Verify and ship

- [x] 7.1 `./run_tests.sh survey -v2` — one baseline before the work, one after; summarize the delta, do not iterate on the runner
- [x] 7.2 Drive the three surfaces in a real browser under a `de` cookie: layer object editor, settings panel, section map picker. The test client cannot see a JS exception
- [x] 7.3 `openspec validate editor-map-js-and-geojson-import --strict`
- [ ] 7.4 Open the PR against `master`; no kill switch and no migration, so rollback is a revert
- [ ] 7.5 After deploy, confirm PostHog issues `01a06dbf-…` (TypeError `'x'`) and the `Geometry has Z dimension` server issue stop receiving events
- [ ] 7.6 Write to `dominik.toennes@viakoeln.de`, who hit all three defects — thank and "fixed", no cause detail
- [x] 7.7 Update the `lesson-l10n-numbers-break-inline-js` memory: the guard reached the templates but not the test, so the next map template inherited the defect
