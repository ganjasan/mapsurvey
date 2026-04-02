## ADDED Requirements

### Requirement: Survey lifecycle status field
The system SHALL store a `status` field on `SurveyHeader` with five possible values: `draft`, `testing`, `published`, `closed`, `archived`. New surveys SHALL default to `draft` status.

#### Scenario: New survey starts as draft
- **WHEN** a user creates a new survey via the editor
- **THEN** the survey's `status` SHALL be `draft`

#### Scenario: Existing surveys migrated to published
- **WHEN** the migration runs on a database with existing surveys
- **THEN** all existing surveys SHALL have `status` set to `published`, except surveys where `is_archived=True` which SHALL have `status` set to `archived`

### Requirement: Valid state transitions
The system SHALL enforce a defined set of valid state transitions. Attempting an invalid transition SHALL fail with an error message.

#### Scenario: Draft to testing
- **WHEN** a survey owner transitions a draft survey to `testing`
- **THEN** the status changes to `testing`

#### Scenario: Draft to published
- **WHEN** a survey owner transitions a draft survey to `published`
- **THEN** the status changes to `published`

#### Scenario: Testing to draft
- **WHEN** a survey owner transitions a testing survey back to `draft`
- **THEN** the status changes to `draft`

#### Scenario: Testing to published
- **WHEN** a survey owner transitions a testing survey to `published`
- **THEN** the status changes to `published`

#### Scenario: Published to closed
- **WHEN** a survey owner transitions a published survey to `closed`
- **THEN** the status changes to `closed`

#### Scenario: Closed to published (reopen)
- **WHEN** a survey owner transitions a closed survey to `published`
- **THEN** the status changes to `published`

#### Scenario: Closed to archived
- **WHEN** a survey owner transitions a closed survey to `archived`
- **THEN** the status changes to `archived` and `is_archived` is set to `True`

#### Scenario: Archived is terminal
- **WHEN** a survey owner attempts to transition an archived survey to any other status
- **THEN** the transition SHALL fail with error "Cannot transition from archived"

#### Scenario: Invalid transition rejected
- **WHEN** a survey owner attempts to transition a draft survey directly to `closed`
- **THEN** the transition SHALL fail with error "Cannot transition from draft to closed"

### Requirement: Transition pre-conditions
The system SHALL validate pre-conditions before allowing certain transitions.

#### Scenario: Draft to testing requires password
- **WHEN** a survey owner attempts to transition to `testing` and the survey has no password set
- **THEN** the transition SHALL fail with error "Testing state requires a password"

#### Scenario: Draft to testing requires structure
- **WHEN** a survey owner attempts to transition to `testing` and the survey has no sections or no questions
- **THEN** the transition SHALL fail with error "Survey must have at least one section with questions"

#### Scenario: Draft to published requires structure
- **WHEN** a survey owner attempts to transition to `published` and the survey has no head section
- **THEN** the transition SHALL fail with error "Survey must have at least one section with questions"

#### Scenario: Draft to testing requires head section
- **WHEN** a survey owner attempts to transition to `testing` and the survey has sections but none marked `is_head=True`
- **THEN** the transition SHALL fail with error "Survey must have a head section"

### Requirement: Test data cleanup on publish
The system SHALL offer to delete test session data when transitioning from `testing` to `published`.

#### Scenario: Clear test data on publish
- **WHEN** a survey owner transitions from `testing` to `published` with `clear_test_data=true`
- **THEN** all `SurveySession` objects for that survey SHALL be deleted (cascading to `Answer`)

#### Scenario: Keep test data on publish
- **WHEN** a survey owner transitions from `testing` to `published` with `clear_test_data=false`
- **THEN** existing `SurveySession` objects SHALL be preserved

### Requirement: Transition endpoint
The system SHALL provide a POST endpoint at `/editor/surveys/<uuid>/transition/` for changing survey status. Only survey owners SHALL be authorized.

#### Scenario: Successful transition via HTMX
- **WHEN** a survey owner sends POST to `/editor/surveys/<uuid>/transition/` with `status=published`
- **THEN** the survey status is updated and the response is HTTP 204

#### Scenario: Failed transition returns error
- **WHEN** a survey owner sends POST with an invalid target status
- **THEN** the response is HTTP 400 with the validation error message

#### Scenario: Non-owner denied
- **WHEN** a survey editor (not owner) sends POST to the transition endpoint
- **THEN** the response is HTTP 403
