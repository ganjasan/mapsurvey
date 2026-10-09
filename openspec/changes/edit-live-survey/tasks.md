## 1. Classifier
- [x] 1.1 `versioning`: `is_live`, `answered_choice_counts` (shared with `check_draft_compatibility`), `removed_answered_choices`, `structural_question_changes`, `structural_section_changes`
- [x] 1.2 Tests per edit kind (`LiveSurveyEditingTest`)

## 2. Safe edits in place
- [x] 2.1 `_edit_locks` / `_check_content_edit_allowed` in question edit, section detail, sub-question share, section map picker; structural endpoints keep `_check_structural_edit_allowed`
- [x] 2.2 `is_read_only` (nothing editable) split from `structure_locked` (structure gated) in every editor template
- [x] 2.3 Live-wording hint in the question modal; type shown read-only with "Change type…"
- [x] 2.4 Kill switch `LIVE_SURVEY_EDITING`; viewers still see the survey read-only

## 3. Unpublished changes
- [x] 3.1 `editor_create_draft` takes `then` + `section_code`, lands on the matching section; `add_question` / `add_section` replayed
- [x] 3.2 Gate modal on every viewport (`data-gate` controls, drag handles); "Change structure" in the context bar, "✎ Structure" on mobile
- [x] 3.3 `editor_survey_detail` redirects to the draft unless `?live=1`; "View live version"; live edits refused while a draft exists
- [x] 3.4 Title without "Draft of"; "Unpublished changes" pill and status chip; dashboard badge

## 4. Vocabulary
- [x] 4.1 Publish changes / Discard changes in the context bar, mobile bar, account menu and modals
- [ ] 4.2 Translations — deferred with the general catalog refresh (design: Translations)
- [x] 4.3 Changelog entry `survey/changelog/2026-10-09-edit-live-surveys.html`

## 5. Measurement
- [x] 5.1 `pe` events: live_edit_saved, unpublished_changes_started/published/discarded; browser `structure_gate_shown`
- [x] 5.2 Existing tests that describe the read-only page run with the switch off (`ReadOnlyLockTest`, `EditorSubquestionTest`, `SurveyStatusLineTest`); full suite: the only failures are the three that fail on main too (`CreateSurveyWizardTest` ×2, `RussianLandingHreflangTest`)
