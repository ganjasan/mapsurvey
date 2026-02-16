## ADDED Requirements

### Requirement: Draft surveys blocked from public access
The system SHALL return HTTP 404 when an unauthenticated user or a user without editor/owner role accesses a survey with `status=draft` via any public URL.

#### Scenario: Anonymous user accesses draft survey
- **WHEN** an unauthenticated user navigates to `/surveys/<uuid>/` for a draft survey
- **THEN** the system SHALL return HTTP 404

#### Scenario: Editor/owner can access draft survey
- **WHEN** an authenticated user with editor or owner role on the survey navigates to `/surveys/<uuid>/`
- **THEN** the system SHALL allow access and render the survey normally

### Requirement: Testing surveys require token or password
The system SHALL require either a valid test token in the URL query parameter or a password to access a survey with `status=testing`. Survey editors/owners SHALL bypass this check.

#### Scenario: Access with valid test token
- **WHEN** a user navigates to `/surveys/<uuid>/?token=<valid-test-token>`
- **THEN** the system SHALL allow access and store token validation in the session

#### Scenario: Access with invalid test token
- **WHEN** a user navigates to `/surveys/<uuid>/?token=<invalid-token>` without prior password authentication
- **THEN** the system SHALL render the password entry page

#### Scenario: Access with session token
- **WHEN** a user previously accessed the testing survey with a valid token and navigates to another section
- **THEN** the system SHALL allow access without requiring the token in the URL again

#### Scenario: Access with password
- **WHEN** a user has authenticated via the password entry page for this survey
- **THEN** the system SHALL allow access to the testing survey

#### Scenario: Access without token or password
- **WHEN** an unauthenticated user navigates to `/surveys/<uuid>/` for a testing survey without token or prior password authentication
- **THEN** the system SHALL render the password entry page

### Requirement: Published surveys with optional password
The system SHALL allow open access to published surveys without a password. If a password is set, the system SHALL require password authentication before allowing access.

#### Scenario: Published survey without password
- **WHEN** a user navigates to `/surveys/<uuid>/` for a published survey with no password set
- **THEN** the system SHALL allow access without any authentication

#### Scenario: Published survey with password
- **WHEN** a user navigates to `/surveys/<uuid>/` for a published survey with a password set and the user has not yet authenticated
- **THEN** the system SHALL render the password entry page

#### Scenario: Published survey after password entry
- **WHEN** a user has entered the correct password for a published survey
- **THEN** the system SHALL allow access to all sections of the survey without re-entering the password

### Requirement: Closed and archived surveys block new responses
The system SHALL prevent new survey sessions from being created for surveys with `status` of `closed` or `archived`. The system SHALL render a "survey closed" page instead.

#### Scenario: New visitor to closed survey
- **WHEN** a user without an active session navigates to `/surveys/<uuid>/` for a closed survey
- **THEN** the system SHALL render a "survey closed" page with the survey name and a message

#### Scenario: New visitor to archived survey
- **WHEN** a user navigates to `/surveys/<uuid>/` for an archived survey
- **THEN** the system SHALL render a "survey closed" page

#### Scenario: Editor can still view closed survey
- **WHEN** an authenticated user with editor or owner role navigates to a closed survey's public URL
- **THEN** the system SHALL allow access

### Requirement: Access control applied to all public survey views
The system SHALL apply access control checks to `survey_header`, `survey_section`, `survey_language_select`, and `survey_thanks` views.

#### Scenario: Access check on survey_section
- **WHEN** a user navigates directly to `/surveys/<uuid>/<section_name>/` for a draft survey
- **THEN** the system SHALL return HTTP 404

#### Scenario: Access check on language selection
- **WHEN** a user navigates to `/surveys/<uuid>/language/` for a closed survey
- **THEN** the system SHALL render the "survey closed" page

#### Scenario: Thanks page accessible after completion
- **WHEN** a user completes a published survey and is redirected to `/surveys/<uuid>/thanks/`
- **THEN** the system SHALL render the thanks page regardless of access control (session was already active)
