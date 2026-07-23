## MODIFIED Requirements

### Requirement: Authenticated users can delete surveys
The system SHALL allow authenticated users to move surveys to trash from the editor page. Unauthenticated users MUST be redirected to the login page.

#### Scenario: Delete button visible for authenticated user
- **WHEN** an authenticated user views the editor page
- **THEN** each survey row SHALL display a functional Delete link

#### Scenario: Unauthenticated user redirected
- **WHEN** an unauthenticated user attempts to access the delete endpoint
- **THEN** the system SHALL redirect to the login page

### Requirement: Delete requires confirmation
The system SHALL display a confirmation modal before moving a survey to trash. The modal MUST show the survey name and MUST state that the survey can be restored from Trash within 30 days.

#### Scenario: Confirmation modal displays survey name
- **WHEN** user clicks the Delete link for a survey
- **THEN** a modal SHALL appear naming the survey and mentioning the 30-day Trash recovery window
- **AND** the modal SHALL have Cancel and Delete buttons

#### Scenario: Cancel aborts deletion
- **WHEN** user clicks Cancel in the confirmation modal
- **THEN** no deletion occurs
- **AND** the modal closes

### Requirement: Survey deletion cascades to related data
Cascade removal of related data (sessions, answers, sections, questions, media files) SHALL happen only at permanent purge time (manual Delete-forever or 30-day auto-purge), not when the survey is moved to trash.

#### Scenario: Trashing preserves related data
- **WHEN** a survey with sessions and answers is moved to trash
- **THEN** all its SurveySession, Answer, SurveySection, and Question records SHALL remain in the database

#### Scenario: Related data deleted at purge
- **WHEN** a trashed survey is permanently purged
- **THEN** all SurveySession records for that survey SHALL be deleted
- **AND** all Answer records for those sessions SHALL be deleted
- **AND** all SurveySection records for that survey SHALL be deleted
- **AND** all Question records for those sections SHALL be deleted

### Requirement: Delete action uses POST with CSRF
The delete action MUST use HTTP POST method with valid CSRF token to `/editor/delete/<uuid>/`. GET requests to the delete endpoint SHALL NOT modify data.

#### Scenario: POST request trashes survey
- **WHEN** authenticated user submits POST to `/editor/delete/<uuid>/` with valid CSRF token
- **THEN** the survey matching that UUID SHALL be moved to trash
- **AND** user SHALL be redirected to editor with success message

#### Scenario: Missing CSRF token rejected
- **WHEN** a POST request is made without valid CSRF token
- **THEN** the request SHALL be rejected with 403 error

### Requirement: Deletion feedback via flash messages
The system SHALL provide feedback about trash success or failure via Django messages framework, including a pointer to the Trash view for recovery.

#### Scenario: Successful trash message
- **WHEN** a survey is successfully moved to trash
- **THEN** user is redirected to editor
- **AND** a success message SHALL confirm the move and mention it can be restored from Trash

#### Scenario: Survey not found error
- **WHEN** user attempts to delete a survey with a non-existent UUID
- **THEN** user is redirected to editor
- **AND** an error message is displayed
