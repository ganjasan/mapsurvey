# survey-editor Specification (delta)

## MODIFIED Requirements

### Requirement: Survey creation
The system SHALL provide a form at `/editor/surveys/new/` that allows authenticated users to create a new survey. The form SHALL include fields for survey name, organization, available languages, visibility, redirect URL, and thanks HTML, and — when an LLM provider is configured — an optional AI brief panel (goal, audience, map target, use-case) with a "Generate draft" action alongside the manual "Create empty" action. A manual submission (the "Create empty" action, or any POST without an explicit action) SHALL create a SurveyHeader (with auto-generated UUID) and one default section (marked `is_head=True`), then redirect to the survey editor using the UUID — byte-identical to the pre-AI behavior. A "Generate draft" submission SHALL follow the asynchronous generation flow defined in the `ai-survey-generation` capability and, on success, redirect to the populated survey's editor.

#### Scenario: Create a new survey
- **WHEN** an authenticated user submits the survey creation form with name "my_test_survey" using the manual action
- **THEN** a SurveyHeader with that name and auto-generated UUID is created, a default section with `is_head=True` is created, and the user is redirected to `/editor/surveys/<uuid>/`

#### Scenario: Duplicate survey name allowed
- **WHEN** a user submits the creation form with a name that already exists for another user's survey
- **THEN** the survey SHALL be created successfully (names are not globally unique)

#### Scenario: Unauthenticated access denied
- **WHEN** an unauthenticated user accesses `/editor/surveys/new/`
- **THEN** the system redirects to the login page

#### Scenario: Legacy POST without action falls back to manual creation
- **WHEN** a POST reaches the view without an `action` parameter
- **THEN** the manual creation path runs exactly as before the AI panel existed

#### Scenario: Generate draft action
- **WHEN** an authenticated editor submits the form with the "Generate draft" action, a filled brief, and a configured provider
- **THEN** generation is enqueued and the page enters the polling state defined in `ai-survey-generation`, ending on success at the populated survey's editor

## ADDED Requirements

### Requirement: New-user redirect to survey creation
The `/editor/` dashboard SHALL redirect users whose active organization has zero
canonical, non-deleted surveys — and whose role permits creating surveys — to
`/editor/surveys/new/?welcome=1`. The redirect SHALL be suppressed by the query parameter
`dashboard=1`; the create page SHALL expose a "Skip to dashboard" escape link carrying
that parameter, and its Cancel link SHALL carry it as well so no redirect loop is
possible.

#### Scenario: Empty org lands on create page
- **WHEN** an editor-or-higher user with no surveys in the active org opens `/editor/`
- **THEN** they are redirected to `/editor/surveys/new/?welcome=1` and the page shows a "Skip to dashboard" link

#### Scenario: Explicit dashboard access
- **WHEN** the same user opens `/editor/?dashboard=1`
- **THEN** the dashboard renders (empty state) without redirecting

#### Scenario: Org with surveys unaffected
- **WHEN** a user whose active org has at least one canonical non-deleted survey opens `/editor/`
- **THEN** the dashboard renders as today with no redirect

#### Scenario: Viewer role not redirected
- **WHEN** a viewer-role user in a zero-survey org opens `/editor/`
- **THEN** the dashboard renders normally (the viewer cannot create surveys, so the create page would be a dead end)
