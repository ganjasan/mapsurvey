## MODIFIED Requirements

### Requirement: Export survey to ZIP via Web UI
The system SHALL provide export options in `/editor/` dashboard. Export SHALL be restricted to users with at least "viewer" effective role for the survey.

#### Scenario: Export with mode selection
- **WHEN** an authenticated user with at least "viewer" effective role clicks "Export" for a survey
- **THEN** system shows dropdown with options: Structure, Data, Full

#### Scenario: Dropdown visual feedback
- **WHEN** user hovers over export dropdown item
- **THEN** item background SHALL highlight (light gray)
- **WHEN** user clicks/presses dropdown item
- **THEN** item background SHALL change to primary color (blue) with white text

#### Scenario: Download export
- **WHEN** user selects export mode
- **THEN** browser downloads ZIP file named `survey_<name>_<mode>.zip`

#### Scenario: Unauthenticated access
- **WHEN** unauthenticated user accesses export URL directly
- **THEN** system redirects to login page

#### Scenario: No access to survey
- **WHEN** a user with no effective role for the survey accesses the export URL
- **THEN** the system SHALL return 404

### Requirement: Import survey from ZIP via Web UI
The system SHALL provide an upload form in `/editor/` dashboard to import surveys. Import SHALL be restricted to users with org role "editor" or higher. Imported surveys SHALL be assigned to the active organization with the importing user as survey owner.

#### Scenario: Import from editor
- **WHEN** an authenticated user with org role "editor" or higher clicks "Import Survey" and uploads ZIP file
- **THEN** system imports survey with organization=active_org and created_by=current_user
- **AND** a SurveyCollaborator with user=current_user, role="owner" is created
- **AND** user is redirected to `/editor/` with success message

#### Scenario: Import validation error in Web UI
- **WHEN** user uploads invalid archive via Web UI
- **THEN** system shows error message on same page without redirect

#### Scenario: Unauthenticated upload
- **WHEN** unauthenticated user accesses import URL directly
- **THEN** system redirects to login page

#### Scenario: Viewer cannot import
- **WHEN** a user with org role "viewer" attempts to import a survey
- **THEN** the system SHALL return 403

### Requirement: Import creates related objects correctly
The import command SHALL create all related objects in the correct order to satisfy foreign key constraints. When importing via Web UI, the organization SHALL be set to the active organization (ignoring the archive's organization field).

#### Scenario: Import order
- **WHEN** a survey archive is imported via Web UI
- **THEN** objects SHALL be created in this order:
  1. SurveyHeader (organization=active_org, created_by=current_user)
  2. SurveyCollaborator (user=current_user, role="owner")
  3. SurveySections (without next/prev links)
  4. Questions (parents before children) with choices and image extraction
  5. SurveySection next/prev links resolved

#### Scenario: Atomic import transaction
- **WHEN** import fails at any step
- **THEN** all created objects SHALL be rolled back and database remains unchanged

#### Scenario: Reuse existing Organization
- **WHEN** archive specifies an organization name that already exists in database
- **THEN** system SHALL use the existing Organization instead of creating duplicate

#### Scenario: Generate unique question codes with remapping
- **WHEN** archive contains a question with code that already exists in database
- **THEN** system SHALL generate a new unique code and store mapping old_code → new_code

#### Scenario: Apply code remapping to responses
- **WHEN** importing responses.json after question codes were remapped
- **THEN** system SHALL translate answer.question_code using the remapping table

#### Scenario: Apply code remapping to parent references
- **WHEN** question has parent_question reference and parent code was remapped
- **THEN** system SHALL resolve parent using remapped code

#### Scenario: Broken section link warning
- **WHEN** archive contains a section with next_section_name referencing non-existent section
- **THEN** system SHALL set the link to null and output warning "Section '<name>': next_section '<ref>' not found, set to null"
