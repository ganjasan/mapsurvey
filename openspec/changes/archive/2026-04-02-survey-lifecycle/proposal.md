## Why

Surveys currently have no formal lifecycle — they become publicly accessible immediately after creation, can be edited while collecting responses, and have no mechanism for controlled testing or password-gated access. This makes it impossible to prepare a survey, test it with a small group, publish it when ready, and close it when data collection is complete. Adding a lifecycle with explicit states (Draft, Testing, Published, Closed, Archived) gives survey owners control over when and how respondents can access their surveys.

## What Changes

- Add a `status` field to `SurveyHeader` with five states: `draft`, `testing`, `published`, `closed`, `archived`
- Add `password_hash` field to `SurveyHeader` for optional password protection (hashed via Django's `make_password`)
- Add `test_token` field (UUID) to `SurveyHeader` for shareable test access links
- **BREAKING**: Draft surveys are no longer accessible via public URLs (`/surveys/<slug>/`). Previously all surveys were accessible by direct URL regardless of `visibility` setting
- **BREAKING**: Closed and archived surveys reject new responses. Previously only `is_archived` affected landing page display
- Public survey views (`survey_header`, `survey_section`, `survey_language_select`) enforce access control based on `status`
- Landing page excludes draft surveys from listing
- Editor dashboard shows status badges and hides archived surveys by default
- Editor header bar shows status badge with transition actions (Draft → Testing → Published → Closed → Archived)
- Password management modal in editor for setting/removing survey password and copying test link
- When transitioning from Testing to Published, option to bulk-delete test session data
- Serialization exports `status` field; imported surveys default to `draft`
- Existing surveys are migrated to `status=published` to preserve current behavior

## Capabilities

### New Capabilities
- `survey-lifecycle-states`: Status field on SurveyHeader with valid state transitions (draft → testing → published → closed → archived), transition validation (structure completeness checks), and state-specific business rules
- `survey-access-control`: Access enforcement for public survey URLs based on lifecycle state — block draft surveys, require password/token for testing, optional password for published, block closed/archived
- `survey-password-protection`: Shared password mechanism for surveys — set/remove/change password via editor, hash storage, password entry page for respondents, session-based authentication persistence

### Modified Capabilities
- `survey-editor`: Add status badge and lifecycle transition controls to editor header bar; add password management modal; restrict editing behavior based on status
- `survey-serialization`: Export `status` field in survey.json; imported surveys default to `draft` status; password hash and test token excluded from export for security
- `landing-page`: Exclude surveys with `status=draft` from public listing (in addition to existing `visibility` filter)

## Impact

- **Models**: `SurveyHeader` gets 3 new fields (`status`, `password_hash`, `test_token`), new methods for password management and transition validation
- **Views**: All public survey views (`survey_header`, `survey_section`, `survey_language_select`) get access control checks; editor views get 2 new endpoints (transition, password management)
- **Templates**: New templates for password entry page and closed survey page; modified dashboard and editor header templates for status display
- **URLs**: 2-3 new URL patterns for lifecycle endpoints
- **Migrations**: Schema migration for new fields + data migration to set existing surveys to `published`
- **Serialization**: Minor changes to export/import for status field
- **Backward compatibility**: Existing surveys migrated to `published` preserves current behavior; `is_archived` field kept and synced when archiving
