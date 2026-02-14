## ADDED Requirements

### Requirement: SurveyCollaborator model
The system SHALL have a `SurveyCollaborator` model with fields: `user` (FK to User), `survey` (FK to SurveyHeader), `role` (CharField with choices: owner/editor/viewer). The combination of (user, survey) SHALL be unique. When a user creates a survey, a SurveyCollaborator with role="owner" SHALL be created automatically.

#### Scenario: Collaborator created on survey creation
- **WHEN** a user creates a new survey
- **THEN** a SurveyCollaborator is created with user=creator, survey=new_survey, role="owner"

#### Scenario: Duplicate collaborator rejected
- **WHEN** a SurveyCollaborator already exists for user+survey and another is created
- **THEN** the system SHALL raise a unique constraint violation

#### Scenario: Collaborator role choices
- **WHEN** a SurveyCollaborator is created
- **THEN** the role field SHALL accept only: "owner", "editor", "viewer"

### Requirement: SurveyHeader created_by field
The SurveyHeader model SHALL have a `created_by` field (FK to User, nullable, SET_NULL on delete). This field records who originally created the survey.

#### Scenario: created_by set on survey creation
- **WHEN** a user creates a new survey via the editor
- **THEN** SurveyHeader.created_by SHALL be set to the current user

#### Scenario: created_by preserved on edit
- **WHEN** another user edits the survey
- **THEN** SurveyHeader.created_by SHALL remain unchanged

### Requirement: Two-layer permission resolution
The system SHALL resolve effective survey permissions using two layers: org-level role (Membership) provides baseline access, survey-level role (SurveyCollaborator) can override. The effective permission SHALL be the higher of the two.

#### Scenario: Org owner has full access to all surveys
- **WHEN** an org owner accesses any survey in their organization
- **THEN** the effective role SHALL be "owner" (full control) without needing a SurveyCollaborator entry

#### Scenario: Org admin has full access to all surveys
- **WHEN** an org admin accesses any survey in their organization
- **THEN** the effective role SHALL be "owner" (full control) without needing a SurveyCollaborator entry

#### Scenario: Org editor accesses own survey
- **WHEN** an org editor accesses a survey they created
- **THEN** the effective role SHALL be "owner" (from SurveyCollaborator created at survey creation)

#### Scenario: Org editor accesses other's survey without collaborator
- **WHEN** an org editor accesses a survey created by another user and has no SurveyCollaborator entry
- **THEN** the effective role SHALL be none and access SHALL be denied

#### Scenario: Org editor added as collaborator on other's survey
- **WHEN** an org editor has a SurveyCollaborator entry with role="editor" on another user's survey
- **THEN** the effective role SHALL be "editor"

#### Scenario: Org viewer with survey-level editor override
- **WHEN** an org viewer has a SurveyCollaborator entry with role="editor" on a specific survey
- **THEN** the effective role SHALL be "editor" (survey-level overrides org baseline)

#### Scenario: Org viewer without collaborator entry
- **WHEN** an org viewer accesses a survey without a SurveyCollaborator entry
- **THEN** the effective role SHALL be "viewer" (org baseline)

### Requirement: Survey visibility in editor dashboard
The editor dashboard SHALL show only surveys the user has access to within the active organization. Access means: org owner/admin sees all surveys, org editor sees surveys they created or are collaborator on, org viewer sees all surveys (read-only).

#### Scenario: Org owner sees all surveys
- **WHEN** an org owner views the editor dashboard
- **THEN** all surveys in the active organization SHALL be listed

#### Scenario: Org admin sees all surveys
- **WHEN** an org admin views the editor dashboard
- **THEN** all surveys in the active organization SHALL be listed

#### Scenario: Org editor sees own and collaborated surveys
- **WHEN** an org editor views the editor dashboard
- **THEN** only surveys where the user is creator or has a SurveyCollaborator entry SHALL be listed

#### Scenario: Org viewer sees all surveys read-only
- **WHEN** an org viewer views the editor dashboard
- **THEN** all surveys in the active organization SHALL be listed
- **AND** create/edit/delete actions SHALL NOT be displayed

### Requirement: Permission enforcement on editor actions
All editor actions SHALL check the user's effective survey role before proceeding. Insufficient permissions SHALL result in 403 Forbidden.

#### Scenario: Survey creation requires org editor or higher
- **WHEN** a user with org role "viewer" attempts to create a new survey
- **THEN** the system SHALL return 403

#### Scenario: Survey editing requires survey editor or higher
- **WHEN** a user with effective survey role "viewer" attempts to edit a survey
- **THEN** the system SHALL return 403

#### Scenario: Survey deletion requires survey owner or org owner/admin
- **WHEN** a user with effective survey role "editor" attempts to delete a survey
- **THEN** the system SHALL return 403

#### Scenario: Survey export requires at least viewer access
- **WHEN** a user with no access to a survey attempts to export it
- **THEN** the system SHALL return 403

#### Scenario: Survey import requires org editor or higher
- **WHEN** a user with org role "viewer" attempts to import a survey
- **THEN** the system SHALL return 403

#### Scenario: Cross-org access denied
- **WHEN** a user attempts to access a survey belonging to an organization they are not a member of
- **THEN** the system SHALL return 404

### Requirement: Collaborator management UI
The system SHALL provide a collaborator management interface within the survey settings. Survey owners and org owners/admins SHALL be able to add, change, and remove collaborators.

#### Scenario: Collaborator list in survey settings
- **WHEN** a survey owner opens the survey settings
- **THEN** a "Collaborators" section SHALL display all SurveyCollaborator entries with username, email, and role

#### Scenario: Add collaborator
- **WHEN** a survey owner adds a collaborator by selecting an org member and role
- **THEN** a SurveyCollaborator record is created
- **AND** the collaborator list updates to show the new entry

#### Scenario: Only org members can be added as collaborators
- **WHEN** a survey owner attempts to add a user who is not a member of the survey's organization
- **THEN** the system SHALL reject with error "User must be a member of this organization"

#### Scenario: Change collaborator role
- **WHEN** a survey owner changes a collaborator's role from "viewer" to "editor"
- **THEN** the SurveyCollaborator.role is updated to "editor"

#### Scenario: Remove collaborator
- **WHEN** a survey owner removes a collaborator
- **THEN** the SurveyCollaborator record is deleted

#### Scenario: Cannot remove last survey owner
- **WHEN** a survey has only one SurveyCollaborator with role="owner" and removal is attempted
- **THEN** the system SHALL reject with error "Cannot remove the last survey owner"

#### Scenario: Editor cannot manage collaborators
- **WHEN** a user with effective survey role "editor" attempts to add a collaborator
- **THEN** the system SHALL return 403

#### Scenario: Org owner/admin can manage collaborators on any survey
- **WHEN** an org owner/admin opens survey settings for any survey in the org
- **THEN** the collaborator management UI SHALL be accessible

### Requirement: Data migration for existing data
The system SHALL migrate existing data to the new access control model via a data migration.

#### Scenario: Default organization created
- **WHEN** the migration runs
- **THEN** an Organization named "Mapsurvey" with slug "mapsurvey" SHALL be created

#### Scenario: Existing users assigned to default org
- **WHEN** the migration runs
- **THEN** all existing User records SHALL get a Membership with organization="Mapsurvey" and role="owner"

#### Scenario: Existing surveys assigned to default org
- **WHEN** the migration runs
- **THEN** all existing SurveyHeader records with null organization SHALL be assigned to the "Mapsurvey" organization

#### Scenario: SurveyCollaborator created for existing surveys
- **WHEN** the migration runs
- **THEN** for each existing SurveyHeader, a SurveyCollaborator with role="owner" SHALL be created for the first user (by ID) in the "Mapsurvey" organization
