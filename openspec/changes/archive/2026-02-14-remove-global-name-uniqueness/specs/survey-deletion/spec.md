## MODIFIED Requirements

### Requirement: Delete action uses POST with CSRF
The delete action MUST use HTTP POST method with valid CSRF token to `/editor/delete/<uuid>/`. GET requests to the delete endpoint SHALL NOT delete data.

#### Scenario: POST request deletes survey
- **WHEN** authenticated user submits POST to `/editor/delete/<uuid>/` with valid CSRF token
- **THEN** the survey matching that UUID SHALL be deleted
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
- **WHEN** user attempts to delete a survey with a non-existent UUID
- **THEN** user is redirected to editor
- **AND** an error message is displayed
