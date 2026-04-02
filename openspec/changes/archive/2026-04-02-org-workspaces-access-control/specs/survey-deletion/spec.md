## MODIFIED Requirements

### Requirement: Authenticated users can delete surveys
The system SHALL allow authenticated users with effective survey role "owner" or org role "owner"/"admin" to delete surveys from the editor page. Other roles SHALL NOT see the delete button. Unauthenticated users MUST be redirected to the login page.

#### Scenario: Delete button visible for survey owner
- **WHEN** a user with effective survey role "owner" views the editor page
- **THEN** the survey row SHALL display a functional Delete link

#### Scenario: Delete button visible for org owner/admin
- **WHEN** an org owner or admin views the editor page
- **THEN** each survey row SHALL display a functional Delete link

#### Scenario: Delete button hidden for survey editor
- **WHEN** a user with effective survey role "editor" (not owner) views the editor page
- **THEN** the survey row SHALL NOT display a Delete link

#### Scenario: Delete button hidden for viewer
- **WHEN** a user with effective survey role "viewer" views the editor page
- **THEN** the survey row SHALL NOT display a Delete link

#### Scenario: Unauthenticated user redirected
- **WHEN** an unauthenticated user attempts to access the delete endpoint
- **THEN** the system SHALL redirect to the login page

### Requirement: Delete action uses POST with CSRF
The delete action MUST use HTTP POST method with valid CSRF token to `/editor/delete/<uuid>/`. GET requests to the delete endpoint SHALL NOT delete data. The system SHALL verify the user has effective survey role "owner" or org role "owner"/"admin" before deleting.

#### Scenario: POST request deletes survey
- **WHEN** a user with effective survey role "owner" submits POST to `/editor/delete/<uuid>/` with valid CSRF token
- **THEN** the survey matching that UUID SHALL be deleted
- **AND** all SurveyCollaborator records for that survey SHALL be deleted
- **AND** user SHALL be redirected to editor with success message

#### Scenario: Insufficient permissions rejected
- **WHEN** a user with effective survey role "editor" submits POST to `/editor/delete/<uuid>/`
- **THEN** the system SHALL return 403

#### Scenario: Missing CSRF token rejected
- **WHEN** a POST request is made without valid CSRF token
- **THEN** the request SHALL be rejected with 403 error

#### Scenario: Cross-org delete denied
- **WHEN** a user attempts to delete a survey belonging to a different organization
- **THEN** the system SHALL return 404
