## 1. The shared module

- [x] 1.1 `survey/assets/js/panel_autosave.js`: `PanelAutosave.attach(form, opts)` with `beforeSave`, `exclude`, `onSaved`, `statusEl`, `debounceMs`
- [x] 1.2 Validation path: parse a 400 `{errors}`, resolve the field's visible label, set the status to `Not saved — <Label>: <message>`, mark the field `is-invalid`, offer no retry
- [x] 1.3 Transport path: any other failure sets a retry state; a click on the status re-sends, and only in that state
- [x] 1.4 A successful save clears the status, the field marks and the queued state
- [x] 1.5 `editor_base.html`: load the module once; add the `is-invalid` style next to the existing `.autosave-status` rules

## 2. The dead end itself

- [x] 2.0 `editor_autosave.js`: attach only to forms with `hx-post`, so the question autosaver stops claiming panel forms, POSTing to "null" and writing its error into the map indicator
- [x] 2.1 `SurveyHeaderForm`: `redirect_url` optional, empty normalised to `"#"` in `clean_redirect_url` — no migration, the model already defaults to it

## 3. The three panels

- [x] 3.1 `survey_settings_panel.html`: drop the inline autosaver, call `PanelAutosave.attach`, keep the `sectionSaved` dispatch through `onSaved`, keep `#ref-layers-card` excluded and add the auto-center switch to the exclusions
- [x] 3.2 `thanks_panel.html`: drop the inline autosaver, pass the Quill `syncCurrent()` as `beforeSave` and `refreshBuildPreview` as `onSaved`
- [x] 3.3 `public_results.html`: drop the inline autosaver, keep `data-no-autosave` on the slug field as `exclude`, keep `reloadPreview` as `onSaved`, and keep the slug Apply button posting the slug explicitly

## 4. Tests and verification

- [x] 4.1 Template tests (GIVEN/WHEN/THEN) in a new `PanelAutosaveTest`: each of the three panels loads `panel_autosave.js` and defines no autosave status handler of its own; the settings panel excludes the auto-center switch
- [x] 4.2 A server-side test that an empty Redirect URL saves as `"#"`, and that `editor_survey_settings_panel` answers an invalid AJAX POST with 400 and a per-field `errors` map — the contract the client now reads
- [x] 4.3 Drive it in a browser (template tests cannot see JS — `lesson_shared_partial_global_rename`): a bad Redirect URL names the field, a corrected value clears it, the auto-center switch saves with no settings POST
- [x] 4.4 `./run_tests.sh survey`; `collectstatic`
- [ ] 4.5 PR, merge; confirm the replay pattern stops recurring in Replay Vision
