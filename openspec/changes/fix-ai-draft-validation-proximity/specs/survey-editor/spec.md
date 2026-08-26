## MODIFIED Requirements

### Requirement: Survey creation
The system SHALL provide a form at `/editor/surveys/new/` that allows authenticated users to create a new survey. The form SHALL include fields for survey name, organization, available languages, visibility, redirect URL, and thanks HTML, and — when an LLM provider is configured — an optional AI brief panel (goal, audience, map target, use-case) with a "Generate draft" action alongside the manual "Create empty" action. A manual submission (the "Create empty" action, or any POST without an explicit action) SHALL create a SurveyHeader (with auto-generated UUID) and one default section (marked `is_head=True`), then redirect to the survey editor using the UUID — byte-identical to the pre-AI behavior. A "Generate draft" submission SHALL follow the asynchronous generation flow defined in the `ai-survey-generation` capability and, on success, redirect to the populated survey's editor. On the mobile create wizard (`MOBILE_EDITOR_NAV`, viewport <1024px) with `CREATE_STEER_AI` on, choosing the empty action on the goal step SHALL — after the empty-path intercept defined in `ai-survey-generation`, when it applies — submit the empty creation immediately using the current hidden map framing values and redirect to the editor, without presenting the map step; the draft path SHALL continue to present the map step unchanged. With `CREATE_STEER_AI` off, the wizard's empty path SHALL continue to the map step as before.

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

#### Scenario: Wizard empty path skips the map step
- **WHEN** a creator on the mobile wizard with a blank goal taps "Skip and start from scratch" on the goal step
- **THEN** the empty survey is created with the default map framing from the hidden position fields and the creator lands in the editor without seeing the "Where?" step

#### Scenario: Wizard draft path keeps the map step
- **WHEN** a creator on the mobile wizard fills the goal and taps "✨ Next — choose the place"
- **THEN** the map step is presented and the create action dispatches to the draft path, unchanged by this change

#### Scenario: Wizard empty path with flag off
- **WHEN** `CREATE_STEER_AI` is off and a creator on the mobile wizard taps "Skip and start from scratch"
- **THEN** the wizard continues to the map step, as before this change
