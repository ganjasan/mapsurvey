## 0. Working checkout

- [x] 0.1 New worktree off `origin/master` (never off this checkout — see the parallel-migration lesson): `git worktree add ../Mapsurvey-rename -b feature/inline-rename-survey-title origin/master`
- [x] 0.2 Bootstrap it: `env` symlink, `.env` copy, a fresh `PORT_OFFSET` in `.env.ports` (update the registry comment), `collectstatic`
- [x] 0.3 Reproduce the complaint first: open the editor, click the survey name, observe nothing happens

## 1. Read the five headers before changing any

- [x] 1.1 Read the `.survey-name` block in `survey_detail.html`, `survey_settings.html`, `survey_share.html`, `analytics_dashboard.html`, `public_results.html` and note every difference (only `survey_detail` has the `is_draft_copy` branch — confirm)
- [x] 1.2 Check `survey_create.html`'s hard-coded `New Survey` span — it has no survey yet and stays as it is
- [x] 1.3 Confirm no CSS or JS selects `.survey-name` for anything other than styling (`editor-mobile.css:140`, `editor_base.html:75`)

## 2. Shared title partial

- [x] 2.1 Add `editor/partials/_survey_title.html` rendering the name, the `Draft of …` branch, and — only when the viewer is an owner and the survey is not a draft copy — the editable control
- [x] 2.2 Replace the span in all five templates with the include
- [~] 2.3 Verify each of the five pages still renders its title, at desktop and below 768px — desktop verified; below 768px NOT verified (window resize had no effect on the viewport in the review environment)

## 3. Rename endpoint

- [x] 3.1 Add a single-field `ModelForm` on `SurveyHeader` (name only) in `editor_forms.py`
- [x] 3.2 Add `editor_survey_rename` (POST, `@survey_permission_required('owner')`) returning `{"ok": true, "name": …}` or 400 `{"ok": false, "errors": …}`; register the URL
- [x] 3.3 Tests: owner renames; non-owner is refused and the name is unchanged; over-length rejected, not truncated; whitespace-only rejected; a survey with non-default languages/basemaps/visibility/cover image keeps all of them across a rename

## 4. Inline editing behaviour

- [x] 4.1 `editor_survey_rename.js`: click and keyboard activation enter edit mode, Enter and blur save, Escape restores, an unchanged value sends nothing
- [x] 4.2 Send with `keepalive` so a blur caused by clicking a navbar link is not dropped by the navigation
- [x] 4.3 Render the saved name from the server's response, not from the input
- [x] 4.4 On a 400, keep edit mode with the error visible; on a network failure keep the typed value and say the save failed — never silently show the new name unsaved
- [x] 4.5 `maxlength` + a counter appearing as the limit nears; same treatment on the settings field

## 5. Settings field wording

- [x] 5.1 Change the `name` field's label and its `survey_name` placeholder (`editor_forms.py:114`) to survey-title wording; keep the field itself
- [x] 5.2 Add the strings to the locale catalogs and recompile — Python-side form labels do not show up in a template sweep

## 6. Verify in a browser, not only in tests

- [~] 6.1 Rename from each of the five pages; reload and confirm the new name; check the dashboard card shows it — verified from Survey and Responses, reload confirmed; the dashboard card was not re-checked
- [ ] 6.2 NOT DONE — below 768px: entering edit mode does not reflow the navbar grid or push the version chip / ⋯ overflow off row 1
- [x] 6.3 Type a name at exactly the limit and one over; confirm the counter and the rejection
- [ ] 6.4 NOT DONE in a browser — both covered by tests (SurveyInlineRenameTest), neither checked on the respondent page
- [x] 6.5 Run the template-comment guard test right after editing templates, and `./run_tests.sh survey` once at the end
