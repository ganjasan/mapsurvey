## MODIFIED Requirements

### Requirement: Survey creation
The system SHALL provide a form at `/editor/surveys/new/` that allows authenticated users with org role "editor" or higher to create a new survey. The form SHALL include fields for survey name, available languages, visibility, redirect URL, and thanks HTML. Organization SHALL be auto-assigned to the active organization (not user-selectable). On successful creation, the system SHALL create a SurveyHeader (with auto-generated UUID, organization=active_org, created_by=current_user), one default section (marked `is_head=True`), and a SurveyCollaborator (user=current_user, role="owner"), then redirect to the survey editor using the UUID.

#### Scenario: Create a new survey
- **WHEN** an authenticated user with org role "editor" or higher submits the survey creation form with name "my_test_survey"
- **THEN** a SurveyHeader with that name, auto-generated UUID, organization=active_org, and created_by=current_user is created
- **AND** a default section with `is_head=True` is created
- **AND** a SurveyCollaborator with user=current_user, role="owner" is created
- **AND** the user is redirected to `/editor/surveys/<uuid>/`

#### Scenario: Duplicate survey name allowed
- **WHEN** a user submits the creation form with a name that already exists for another user's survey
- **THEN** the survey SHALL be created successfully (names are not globally unique)

#### Scenario: Unauthenticated access denied
- **WHEN** an unauthenticated user accesses `/editor/surveys/new/`
- **THEN** the system redirects to the login page

#### Scenario: Viewer cannot create surveys
- **WHEN** a user with org role "viewer" accesses `/editor/surveys/new/`
- **THEN** the system SHALL return 403

### Requirement: Survey editor layout
The system SHALL render the survey editor at `/editor/surveys/<uuid>/` as a 3-column layout: a left sidebar listing sections, a center panel showing the selected section's details and questions, and a right panel showing a live preview iframe. The editor page SHALL load HTMX and SortableJS from CDN. The system SHALL verify the user has at least "viewer" effective role for the survey before rendering. Users with "viewer" effective role SHALL see a read-only version (edit/delete buttons hidden).

#### Scenario: Editor page loads with sections and questions
- **WHEN** an authenticated user with at least "viewer" effective role navigates to `/editor/surveys/<uuid>/`
- **THEN** the left sidebar shows all sections in linked-list order, the center panel shows the first section's questions, and the right panel shows a live preview of that section

#### Scenario: Selecting a different section
- **WHEN** the user clicks a section in the sidebar
- **THEN** the center panel updates via HTMX to show that section's detail form and questions, and the preview iframe refreshes to show that section

#### Scenario: Read-only mode for viewers
- **WHEN** a user with effective survey role "viewer" views the editor
- **THEN** edit, delete, and create buttons for sections and questions SHALL be hidden
- **AND** drag-and-drop reordering SHALL be disabled

#### Scenario: Access denied for non-members
- **WHEN** a user with no access to the survey navigates to `/editor/surveys/<uuid>/`
- **THEN** the system SHALL return 404

### Requirement: Survey settings editing
The system SHALL provide a settings form (accessible from the editor) to edit SurveyHeader fields: name, available_languages, visibility, redirect_url, and thanks_html. The settings form SHALL also include a collaborator management section. Only users with effective survey role "owner" or org role "owner"/"admin" SHALL be able to access settings.

#### Scenario: Update survey visibility
- **WHEN** the user changes visibility from "private" to "public" and saves
- **THEN** the SurveyHeader.visibility is updated to "public"

#### Scenario: Update available languages
- **WHEN** the user selects ["en", "ru"] as available languages and saves
- **THEN** the SurveyHeader.available_languages is updated to ["en", "ru"]

#### Scenario: Editor role cannot access settings
- **WHEN** a user with effective survey role "editor" attempts to open survey settings
- **THEN** the system SHALL return 403

### Requirement: Dashboard integration
The system SHALL wire the "New Survey" button in `/editor/` to navigate to `/editor/surveys/new/`. The "Edit" link for each survey SHALL navigate to `/editor/surveys/<uuid>/`. The dashboard SHALL only show surveys accessible to the current user within the active organization. Action buttons (Edit, Delete, Export) SHALL be shown or hidden based on the user's effective survey role.

#### Scenario: New Survey button navigates to creation form
- **WHEN** a user with org role "editor" or higher clicks "New Survey" on the dashboard
- **THEN** the browser navigates to `/editor/surveys/new/`

#### Scenario: New Survey button hidden for viewers
- **WHEN** a user with org role "viewer" views the dashboard
- **THEN** the "New Survey" and "Import Survey" buttons SHALL NOT be displayed

#### Scenario: Edit link navigates to editor
- **WHEN** the user clicks "Edit" for a survey on the dashboard
- **THEN** the browser navigates to `/editor/surveys/<uuid>/`

#### Scenario: Delete button hidden for non-owners
- **WHEN** a user with effective survey role "editor" views the dashboard
- **THEN** the "Delete" button for that survey SHALL NOT be displayed
