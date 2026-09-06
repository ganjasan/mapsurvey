# Fix: CreateSurveyWizardTest depends on the developer's `.env`

## Why

`test_flag_on_renders_wizard_chrome` and `test_flag_off_serves_legacy_page` fail on a
clean checkout of master (079d4b3) and pass only on machines whose `.env` carries AI
provider credentials. The create page renders two different button sets depending on
`ai_available` (`ai_client.provider_configured()`): with a provider configured the
empty-path button says "Start with an empty survey" / "Create empty" (the strings the
tests assert), without one the `{% else %}` branch renders a single "Create Survey"
button. The tests never pin the provider, so their outcome tracks the developer's
environment instead of the code. The wizard itself works correctly in both flag
states — this is a test-determinism defect only, no product change.

Backlog: #148 (`bug-create-wizard-tests-fail-on-master.md`).

## What Changes

- Pin the AI provider at class level on `CreateSurveyWizardTest` with
  `@override_settings(AI_PROVIDER='anthropic', ANTHROPIC_API_KEY='sk-test')` — the
  same pattern `test_panel_is_present_when_provider_configured` already uses — so the
  tests exercise the branch they were written against regardless of the host `.env`.

## Impact

- `survey/tests.py` only. No product code, templates, or migrations.
- Specs: none — no requirement changes.
