## ADDED Requirements

### Requirement: Status badge in editor header
The system SHALL display the current lifecycle status as a colored badge in the editor header bar at `/editor/surveys/<uuid>/`. Badge colors: draft=secondary (gray), testing=warning (yellow), published=success (green), closed=info (blue), archived=dark.

#### Scenario: Draft survey shows gray badge
- **WHEN** a user opens the editor for a draft survey
- **THEN** the header SHALL display a gray badge with text "Draft"

#### Scenario: Published survey shows green badge
- **WHEN** a user opens the editor for a published survey
- **THEN** the header SHALL display a green badge with text "Published"

### Requirement: Transition actions in editor header
The system SHALL display a dropdown button next to the status badge with valid transition actions for the current state. Only survey owners SHALL see the dropdown.

#### Scenario: Draft survey shows testing and publish actions
- **WHEN** a survey owner views the editor for a draft survey
- **THEN** the dropdown SHALL show "Move to Testing" and "Publish" actions

#### Scenario: Testing survey shows publish and back-to-draft actions
- **WHEN** a survey owner views the editor for a testing survey
- **THEN** the dropdown SHALL show "Publish" and "Back to Draft" actions

#### Scenario: Published survey shows close action
- **WHEN** a survey owner views the editor for a published survey
- **THEN** the dropdown SHALL show "Close Survey" action

#### Scenario: Closed survey shows reopen and archive actions
- **WHEN** a survey owner views the editor for a closed survey
- **THEN** the dropdown SHALL show "Reopen" and "Archive" actions

#### Scenario: Archived survey shows no transition actions
- **WHEN** a survey owner views the editor for an archived survey
- **THEN** the dropdown SHALL NOT be displayed (archived is terminal)

#### Scenario: Non-owner does not see transition dropdown
- **WHEN** a survey editor (not owner) views the editor
- **THEN** the transition dropdown SHALL NOT be displayed

### Requirement: Publish confirmation dialog
The system SHALL display a confirmation dialog when transitioning from `testing` to `published`, with a checkbox option to delete test responses.

#### Scenario: Publish from testing shows dialog
- **WHEN** a survey owner clicks "Publish" on a testing survey
- **THEN** a modal dialog SHALL appear with a checkbox "Delete all test responses (recommended)" (checked by default) and "Publish" / "Cancel" buttons

#### Scenario: Publish with test data cleanup
- **WHEN** the owner clicks "Publish" in the dialog with the checkbox checked
- **THEN** the system SHALL transition to `published` and delete all survey sessions

#### Scenario: Publish without test data cleanup
- **WHEN** the owner unchecks the checkbox and clicks "Publish"
- **THEN** the system SHALL transition to `published` without deleting sessions

### Requirement: Status badge on dashboard
The system SHALL display a colored status badge next to each survey name in the `/editor/` dashboard table.

#### Scenario: Dashboard shows status for each survey
- **WHEN** a user views the editor dashboard
- **THEN** each survey row SHALL display a status badge with the same color scheme as the editor header

### Requirement: Dashboard archived filter
The system SHALL hide archived surveys from the dashboard by default. A toggle SHALL allow showing/hiding archived surveys.

#### Scenario: Archived surveys hidden by default
- **WHEN** a user views the editor dashboard without query parameters
- **THEN** surveys with `status=archived` SHALL NOT appear in the list

#### Scenario: Show archived surveys
- **WHEN** a user clicks "Show Archived" toggle on the dashboard
- **THEN** all surveys including archived SHALL appear in the list

### Requirement: New survey default status
The system SHALL create new surveys with `status=draft`. The creation form SHALL NOT include a status field.

#### Scenario: Created survey is draft
- **WHEN** a user creates a new survey via `/editor/surveys/new/`
- **THEN** the survey SHALL have `status=draft`

## MODIFIED Requirements

### Requirement: Survey creation
The system SHALL provide a form at `/editor/surveys/new/` that allows authenticated users to create a new survey. The form SHALL include fields for survey name, organization, available languages, visibility, redirect URL, and thanks HTML. On successful creation, the system SHALL create a SurveyHeader (with auto-generated UUID, `status=draft`) and one default section (marked `is_head=True`), then redirect to the survey editor using the UUID.

#### Scenario: Create a new survey
- **WHEN** an authenticated user submits the survey creation form with name "my_test_survey"
- **THEN** a SurveyHeader with that name, auto-generated UUID, and `status=draft` is created, a default section with `is_head=True` is created, and the user is redirected to `/editor/surveys/<uuid>/`

#### Scenario: Duplicate survey name allowed
- **WHEN** a user submits the creation form with a name that already exists for another user's survey
- **THEN** the survey SHALL be created successfully (names are not globally unique)

#### Scenario: Unauthenticated access denied
- **WHEN** an unauthenticated user accesses `/editor/surveys/new/`
- **THEN** the system redirects to the login page
