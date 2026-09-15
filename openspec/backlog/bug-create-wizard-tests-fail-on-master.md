# CreateSurveyWizardTest fails on master (inverted MOBILE_EDITOR_NAV behavior)

**Type**: bug
**Priority**: medium
**Area**: frontend
**Created**: 2026-08-24

## Description

`test_flag_on_renders_wizard_chrome` and `test_flag_off_serves_legacy_page` fail on
clean `origin/master` (079d4b3, after the #108 mobile-adaptive merge). The rendered
page is the opposite of what `override_settings(MOBILE_EDITOR_NAV=...)` requests:
with the flag off the create page shows wizard chrome (`wizard-map-topbar`,
"Start with an empty survey"), with the flag on it shows the legacy page
(no wizard chrome, no "Start with an empty survey").

## Notes

- Reproduced 2026-08-24 while resolving the PR #102 conflict — fails identically in
  isolation and in the full suite, and on a pristine master worktree, so it is not
  caused by that merge.
- The context processor reads the flag correctly at request time
  (`getattr(settings, 'MOBILE_EDITOR_NAV', False)` in `survey/context_processors.py`),
  so the inversion likely lives in how `/editor/surveys/new/` picks its template or in
  the tests' assumptions after #108 rewrote the create page.
- **Root cause found 2026-08-24**: the wizard and the flag both work correctly. The
  create page renders different buttons depending on `ai_available`
  (`ai_client.provider_configured()`): with an AI provider configured the empty-path
  button carries the strings the tests assert; without one the `{% else %}` branch
  renders a single "Create Survey" button. The tests never pin the provider, so they
  pass only on machines whose `.env` has AI keys. Test-determinism defect, no product
  bug. Fix (class-level `override_settings(AI_PROVIDER=..., ANTHROPIC_API_KEY=...)`)
  lives in OpenSpec change `fix-create-wizard-tests-env` on branch
  `fix/create-wizard-tests-env`.
