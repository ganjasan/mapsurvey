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
- [x] 3.3 `editor_survey_detail` redirects to the draft unless `?live=1`; "View live version"; live edits refused while a draft exists — questions, sections and the section map through `_check_content_edit_allowed`; survey settings, the thanks page and the survey map start through `_check_not_shadowed_by_draft` (publish_draft copies those onto the canonical)
- [x] 3.4 Title without "Draft of"; "Unpublished changes" pill and status chip; dashboard badge
- [x] 3.6 Hotfix after release: on phones the full-screen dialogs used `100vh`, which includes the strip behind the browser's URL bar, so "Publish changes" opened with Cancel/Publish below the visible screen — `100dvh` + sticky `.modal-footer` (`editor-mobile.css`)
- [x] 3.5 Editors start unpublished changes (`editor_create_draft` → `editor` role); publish/discard stay owner-only, editors see who publishes

## 4. Vocabulary
- [x] 4.1 Publish changes / Discard changes in the context bar, mobile bar, account menu and modals
- [x] 4.2 Translations — out of scope for this change: the new strings ship in English and go in with the general catalog refresh (design: Translations), which is its own piece of work
- [x] 4.3 Changelog entry `survey/changelog/2026-10-09-edit-live-surveys.html`

## 5. Measurement
- [x] 5.1 `pe` events: live_edit_saved, unpublished_changes_started/published/discarded; browser `structure_gate_shown`
- [x] 5.2 Existing tests that describe the read-only page run with the switch off (`ReadOnlyLockTest`, `EditorSubquestionTest`, `SurveyStatusLineTest`); full suite green — the three tests that were already failing on `master` (`CreateSurveyWizardTest` ×2 assumed a configured AI provider; `RussianLandingHreflangTest` lacked the Solutions-menu string in the `ru` catalog) are fixed here too
