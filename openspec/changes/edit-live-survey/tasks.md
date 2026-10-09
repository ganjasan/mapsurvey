## 1. Classifier
- [ ] 1.1 `versioning.classify_live_edit` + shared "answered choice codes" helper with `check_draft_compatibility`
- [ ] 1.2 Tests per edit kind (safe/structural table from design D1)

## 2. Safe edits in place
- [ ] 2.1 Replace `_check_structural_edit_allowed` with the classifier in question/section/translation/settings views
- [ ] 2.2 `is_read_only` → `is_live`; Build controls for safe fields enabled on live surveys
- [ ] 2.3 "Saved · live" indicator; answered-wording hint
- [ ] 2.4 Kill switch `LIVE_SURVEY_EDITING`

## 3. Unpublished changes
- [ ] 3.1 Endpoint: create draft + replay structural action by code; fallback message
- [ ] 3.2 Inline prompt on first structural action (desktop and mobile; replaces `editIntercept`)
- [ ] 3.3 `editor_survey_detail` redirect to draft unless `?live=1`; "View live version"
- [ ] 3.4 Title without "Draft of"; "Unpublished changes" pill; dashboard badge

## 4. Vocabulary
- [ ] 4.1 Rename buttons/labels in ctx-bar, mobile status bar, publishing widget, modals
- [ ] 4.2 Translations for every creator language
- [ ] 4.3 Changelog entry `survey/changelog/<date>-edit-live-surveys.html`

## 5. Measurement
- [ ] 5.1 `pe` events: live_edit_saved, unpublished_changes_started/published/discarded, read_only_intercept_shown
- [ ] 5.2 Update existing tests that assert 403 on safe edits; full suite green
