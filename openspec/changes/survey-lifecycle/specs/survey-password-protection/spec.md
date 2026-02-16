## ADDED Requirements

### Requirement: Password storage on SurveyHeader
The system SHALL store a hashed password on `SurveyHeader` using Django's `make_password()`. The `password_hash` field SHALL be nullable (no password by default).

#### Scenario: Set password
- **WHEN** a survey owner sets password "test123" on a survey
- **THEN** the `password_hash` field SHALL contain a hash produced by `make_password("test123")`

#### Scenario: Verify correct password
- **WHEN** a user submits password "test123" for a survey with that password set
- **THEN** `check_password("test123", survey.password_hash)` SHALL return `True`

#### Scenario: Reject incorrect password
- **WHEN** a user submits password "wrong" for a survey with password "test123"
- **THEN** `check_password("wrong", survey.password_hash)` SHALL return `False`

#### Scenario: No password by default
- **WHEN** a new survey is created
- **THEN** `password_hash` SHALL be `None`

### Requirement: Password management endpoint
The system SHALL provide a view at `/editor/surveys/<uuid>/password/` for managing the survey password. Only survey owners SHALL be authorized.

#### Scenario: Set password via editor
- **WHEN** a survey owner sends POST with `action=set` and `password=mypass`
- **THEN** the survey's password_hash is updated with the hashed password

#### Scenario: Remove password via editor
- **WHEN** a survey owner sends POST with `action=remove` and the survey is not in `testing` status
- **THEN** the survey's password_hash is set to `None`

#### Scenario: Cannot remove password in testing state
- **WHEN** a survey owner sends POST with `action=remove` and the survey has `status=testing`
- **THEN** the response is HTTP 400 with error "Cannot remove password while in Testing status"

#### Scenario: Password minimum length
- **WHEN** a survey owner sends POST with `action=set` and `password=ab` (less than 4 characters)
- **THEN** the response is HTTP 400 with error "Password must be at least 4 characters"

### Requirement: Test token on SurveyHeader
The system SHALL store a `test_token` (UUID) on `SurveyHeader`, auto-generated on creation.

#### Scenario: Test token auto-generated
- **WHEN** a new survey is created
- **THEN** `test_token` SHALL be a valid UUID4 value

#### Scenario: Regenerate test token
- **WHEN** a survey owner sends POST with `action=regenerate_token`
- **THEN** the survey's `test_token` is replaced with a new UUID4 value

### Requirement: Password entry page
The system SHALL provide a password entry page at `/surveys/<slug>/password/` for respondents to authenticate.

#### Scenario: Render password form
- **WHEN** a user navigates to `/surveys/<slug>/password/` via GET
- **THEN** the system SHALL render a form with a password input field and the survey name

#### Scenario: Correct password submission
- **WHEN** a user submits the correct password via POST
- **THEN** the system SHALL set a session key `survey_password_{survey_id}` to `True` and redirect to `/surveys/<slug>/`

#### Scenario: Incorrect password submission
- **WHEN** a user submits an incorrect password via POST
- **THEN** the system SHALL re-render the form with an "Incorrect password" error message

### Requirement: Password management modal in editor
The system SHALL display a password management modal in the editor, accessible via a button in the editor header. The modal SHALL show password status, allow setting/changing/removing the password, and display the test link URL with a copy button when in testing state.

#### Scenario: Modal shows test link in testing state
- **WHEN** a survey owner opens the password modal for a survey in `testing` status
- **THEN** the modal SHALL display the test URL `/surveys/<uuid>/?token=<test_token>` with a copy button

#### Scenario: Modal shows password status
- **WHEN** a survey owner opens the password modal
- **THEN** the modal SHALL indicate whether a password is currently set

#### Scenario: Modal hidden for archived surveys
- **WHEN** a survey is in `archived` status
- **THEN** the password management button SHALL NOT be displayed in the editor header
