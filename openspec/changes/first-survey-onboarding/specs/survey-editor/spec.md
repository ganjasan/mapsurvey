## MODIFIED Requirements

### Requirement: Survey creation
The system SHALL provide a form at `/editor/surveys/new/` that allows authenticated users to create a new survey. The form SHALL include fields for survey name, organization, available languages, visibility, redirect URL, and thanks HTML, and — when an LLM provider is configured — an optional AI brief panel (goal, audience, map target, use-case) with a "Generate draft" action alongside the manual "Create empty" action. A manual submission (the "Create empty" action, or any POST without an explicit action) SHALL create a SurveyHeader (with auto-generated UUID) and one default section (marked `is_head=True`), then redirect to the survey editor using the UUID — byte-identical to the pre-AI behavior. A "Generate draft" submission SHALL follow the asynchronous generation flow defined in the `ai-survey-generation` capability and, on success, redirect to the populated survey's editor. On the mobile create wizard (`MOBILE_EDITOR_NAV`, viewport <1024px) with `CREATE_STEER_AI` on, choosing the empty action on the goal step SHALL — after the empty-path intercept defined in `ai-survey-generation`, when it applies — submit the empty creation immediately using the current hidden map framing values and redirect to the editor, without presenting the map step; the draft path SHALL continue to present the map step unchanged. With `CREATE_STEER_AI` off, the wizard's empty path SHALL continue to the map step as before. The map picker's initial view SHALL be the position returned by the `map-start-position` chain for the request (never a fixed city), and the page SHALL post that chain's `source` in a hidden `map_source` field. Opened with `?from=start`, the page SHALL replace "Skip and start from scratch" with a link back to `/editor/surveys/start/`; without the parameter it SHALL render as before.

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
- **WHEN** a creator on the mobile wizard fills the goal and taps "✨ Draft my survey"
- **THEN** the map step is presented and the create action dispatches to the draft path, unchanged by this change

#### Scenario: Wizard empty path with flag off
- **WHEN** `CREATE_STEER_AI` is off and a creator on the mobile wizard taps "Skip and start from scratch"
- **THEN** the wizard continues to the map step, as before this change

#### Scenario: Map opens on the suggested centre
- **WHEN** a creator whose organization has a survey positioned in Bishkek opens the create page
- **THEN** the picker's initial view is that position and the hidden `map_source` field is `org_survey`

#### Scenario: Opened from the start page
- **WHEN** the create page is opened with `?from=start`
- **THEN** "Skip and start from scratch" is absent and a link to `/editor/surveys/start/` is shown

### Requirement: Dashboard integration
The system SHALL wire the "New Survey" button in `/editor/` by the creator's
`survey_start_default`: with no default it navigates to `/editor/surveys/start/`; with
`ai` to `/editor/surveys/new/`; with `blank` it is a POST form to
`/editor/surveys/new/blank/`. The dashboard's ⋯ menu SHALL offer "Start another way…"
linking to `/editor/surveys/start/`. The "Edit" link for each survey SHALL navigate to `/editor/surveys/<uuid>/`.

#### Scenario: New Survey button navigates to the start page
- **WHEN** a creator with no start default clicks "New Survey" on the dashboard
- **THEN** the browser navigates to `/editor/surveys/start/`

#### Scenario: New Survey button honours the AI default
- **WHEN** a creator with `survey_start_default='ai'` clicks "New Survey"
- **THEN** the browser navigates to `/editor/surveys/new/`

#### Scenario: New Survey button honours the blank default
- **WHEN** a creator with `survey_start_default='blank'` clicks "New Survey"
- **THEN** a POST creates a blank survey and the editor opens

#### Scenario: Edit link navigates to editor
- **WHEN** the user clicks "Edit" for a survey on the dashboard
- **THEN** the browser navigates to `/editor/surveys/<uuid>/`

### Requirement: New-user redirect to survey creation
The `/editor/` dashboard SHALL redirect users whose active organization has zero
canonical, non-deleted surveys — and whose role permits creating surveys — to
`/editor/surveys/start/?welcome=1`. The redirect SHALL be suppressed by the query parameter
`dashboard=1`; the start page SHALL expose a "Skip to dashboard" escape link carrying
that parameter so no redirect loop is possible. The create page SHALL keep honouring
`?welcome=1` for old links.

#### Scenario: Empty org lands on the start page
- **WHEN** an editor-or-higher user with no surveys in the active org opens `/editor/`
- **THEN** they are redirected to `/editor/surveys/start/?welcome=1` and the page shows a "Skip to dashboard" link

#### Scenario: Explicit dashboard access
- **WHEN** the same user opens `/editor/?dashboard=1`
- **THEN** the dashboard renders (empty state) without redirecting

#### Scenario: Org with surveys unaffected
- **WHEN** a user whose active org has at least one canonical non-deleted survey opens `/editor/`
- **THEN** the dashboard renders as today with no redirect

#### Scenario: Viewer role not redirected
- **WHEN** a viewer-role user in a zero-survey org opens `/editor/`
- **THEN** the dashboard renders normally (the viewer cannot create surveys, so the start page would be a dead end)
