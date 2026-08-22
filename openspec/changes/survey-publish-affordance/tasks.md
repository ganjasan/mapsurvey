## 1. Primary-action include

- [x] 1.1 Add `editor/partials/_survey_primary_action.html`: owner-only, non-archived; branch on `survey.status` → draft: green `Publish` (`doTransition('published')`); testing: green `Publish — open for responses` (`showPublishConfirm()`); published: `● Open` pill + outline `Close` (`doTransition('closed')`); closed: `○ Closed` pill + outline `Reopen` (`doTransition('published')`)
- [x] 1.2 Use `{% comment %}` (never multi-line `{# #}`) and match existing `.btn`/`.pub-chip` classes

## 2. Wire it into both context-bar branches

- [x] 2.1 Editable branch (`survey_detail.html` ~line 53): keep draft-copy `Publish Version`/`Discard` as-is; for the canonical survey, replace the `status == 'draft'`-only publish button with the include so testing also gets a primary action
- [x] 2.2 Read-only branch (~line 26, `published`/`closed`): add the include to the right-hand action group so Open/Close and Closed/Reopen appear there too, visually separate from the edit-a-draft actions
- [x] 2.3 Confirm `_lifecycle_scripts.html` (providing `doTransition`/`showPublishConfirm`) is loaded on this page in every branch

## 3. Tests

- [x] 3.1 draft → context bar has a `Publish` primary action
- [x] 3.2 testing → context bar has `Publish — open for responses` (not only the chip)
- [x] 3.3 published → context bar shows an `Open` state + a `Close` action
- [x] 3.4 closed → context bar shows a `Closed` state + a `Reopen` action
- [x] 3.5 non-owner (viewer) → only `Preview`, no publish/close/reopen
- [x] 3.6 draft-copy → `Publish Version`/`Discard` retained, no collection-status primary action
- [x] 3.7 Run the template comment guard test

## 4. Verify

- [ ] 4.1 `./run_tests.sh survey` green
- [ ] 4.2 Eyeball each status on the dev stand (:8020): the primary action matches the state
