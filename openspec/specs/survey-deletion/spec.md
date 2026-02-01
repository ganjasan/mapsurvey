### Requirement: Authenticated users can delete surveys
The system SHALL allow authenticated users to delete surveys from the editor page. Unauthenticated users MUST be redirected to the login page.

#### Scenario: Delete button visible for authenticated user
- **WHEN** an authenticated user views the editor page
- **THEN** each survey row SHALL display a functional Delete link

#### Scenario: Unauthenticated user redirected
- **WHEN** an unauthenticated user attempts to access the delete endpoint
- **THEN** the system SHALL redirect to the login page

### Requirement: Delete requires confirmation
The system SHALL display a confirmation modal before deleting a survey. The modal MUST show the survey name to prevent accidental deletion.

#### Scenario: Confirmation modal displays survey name
- **WHEN** user clicks the Delete link for a survey
- **THEN** a modal SHALL appear with the text "Delete survey '<survey-name>'?"
- **AND** the modal SHALL have Cancel and Delete buttons

#### Scenario: Cancel aborts deletion
- **WHEN** user clicks Cancel in the confirmation modal
- **THEN** no deletion occurs
- **AND** the modal closes

### Requirement: Survey deletion cascades to related data
When a survey is deleted, all related data SHALL be removed including sessions, answers, sections, and questions.

#### Scenario: Related data deleted with survey
- **WHEN** a survey with sessions and answers is deleted
- **THEN** all SurveySession records for that survey SHALL be deleted
- **AND** all Answer records for those sessions SHALL be deleted
- **AND** all SurveySection records for that survey SHALL be deleted
- **AND** all Question records for those sections SHALL be deleted

### Requirement: Delete action uses POST with CSRF
The delete action MUST use HTTP POST method with valid CSRF token. GET requests to the delete endpoint SHALL NOT delete data.

#### Scenario: POST request deletes survey
- **WHEN** authenticated user submits POST to delete endpoint with valid CSRF token
- **THEN** the survey SHALL be deleted
- **AND** user SHALL be redirected to editor with success message

#### Scenario: Missing CSRF token rejected
- **WHEN** a POST request is made without valid CSRF token
- **THEN** the request SHALL be rejected with 403 error

### Requirement: Deletion feedback via flash messages
The system SHALL provide feedback about deletion success or failure via Django messages framework.

#### Scenario: Successful deletion message
- **WHEN** a survey is successfully deleted
- **THEN** user is redirected to editor
- **AND** a success message "Survey '<name>' deleted successfully" is displayed

#### Scenario: Survey not found error
- **WHEN** user attempts to delete a non-existent survey
- **THEN** user is redirected to editor
- **AND** an error message is displayed
