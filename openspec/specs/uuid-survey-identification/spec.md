## ADDED Requirements

### Requirement: SurveyHeader UUID field
The system SHALL have a `uuid` field on `SurveyHeader` of type `UUIDField` with `default=uuid.uuid4`, `unique=True`, `editable=False`. The UUID SHALL be auto-generated on creation and SHALL NOT change after creation.

#### Scenario: New survey gets UUID on creation
- **WHEN** a new SurveyHeader is created
- **THEN** the `uuid` field SHALL be automatically populated with a valid UUID v4

#### Scenario: UUID is unique across all surveys
- **WHEN** two surveys are created
- **THEN** each SHALL have a distinct UUID

#### Scenario: UUID is immutable
- **WHEN** a survey is saved with a modified UUID value
- **THEN** the system SHALL NOT allow the UUID to change (enforced by `editable=False`)

### Requirement: Survey name is not globally unique
The `SurveyHeader.name` field SHALL NOT have a database-level unique constraint. Multiple surveys MAY have the same name.

#### Scenario: Two surveys with same name
- **WHEN** two surveys are created with name "DEMO"
- **THEN** both SHALL be created successfully with different UUIDs

#### Scenario: Name field retains validation rules
- **WHEN** a survey is created with name "my_survey"
- **THEN** the `validate_url_name` validator SHALL still apply (alphanumeric and underscore only)

### Requirement: Editor URLs use UUID
All editor routes SHALL use `<uuid:survey_uuid>` instead of `<str:survey_name>` as the survey identifier in URL patterns.

#### Scenario: Editor survey detail URL
- **WHEN** an authenticated user navigates to `/editor/surveys/<uuid>/`
- **THEN** the system SHALL look up the survey by UUID and render the editor

#### Scenario: Editor URL with invalid UUID returns 404
- **WHEN** a user navigates to `/editor/surveys/not-a-uuid/`
- **THEN** the system SHALL return 404

#### Scenario: Export URL uses UUID
- **WHEN** an authenticated user accesses `/editor/export/<uuid>/`
- **THEN** the system SHALL export the survey identified by that UUID

#### Scenario: Delete URL uses UUID
- **WHEN** an authenticated user POSTs to `/editor/delete/<uuid>/`
- **THEN** the system SHALL delete the survey identified by that UUID

### Requirement: Public URLs support dual lookup
Public survey routes (`/surveys/<survey_slug>/...`) SHALL accept either a UUID string or a survey name. The system SHALL resolve the survey using a helper function with the following lookup order:

1. Attempt to parse `survey_slug` as UUID → look up by `SurveyHeader.uuid`
2. If not a valid UUID, look up by `SurveyHeader.name`
3. If name lookup returns multiple results, return 404

#### Scenario: Public URL with UUID
- **WHEN** a visitor navigates to `/surveys/<valid-uuid>/`
- **THEN** the system SHALL resolve the survey by UUID

#### Scenario: Public URL with unique name
- **WHEN** a visitor navigates to `/surveys/my_survey/` and only one survey has name "my_survey"
- **THEN** the system SHALL resolve the survey by name

#### Scenario: Public URL with ambiguous name
- **WHEN** a visitor navigates to `/surveys/DEMO/` and two surveys have name "DEMO"
- **THEN** the system SHALL return 404

#### Scenario: Public URL with nonexistent slug
- **WHEN** a visitor navigates to `/surveys/nonexistent/`
- **THEN** the system SHALL return 404

### Requirement: Dashboard and template links use UUID
All links to surveys in dashboard and editor templates SHALL use `survey.uuid` to build URLs. Public-facing templates (landing page, survey list) SHALL also use `survey.uuid` for unambiguous linking.

#### Scenario: Dashboard edit link uses UUID
- **WHEN** the editor dashboard renders a survey row
- **THEN** the "Edit" link SHALL point to `/editor/surveys/<uuid>/`

#### Scenario: Dashboard export link uses UUID
- **WHEN** the editor dashboard renders export options
- **THEN** export links SHALL point to `/editor/export/<uuid>/`

#### Scenario: Dashboard delete link uses UUID
- **WHEN** the editor dashboard renders a delete action
- **THEN** the delete form/link SHALL target `/editor/delete/<uuid>/`

#### Scenario: Landing page survey links use UUID
- **WHEN** the landing page renders survey cards
- **THEN** each card link SHALL use `/surveys/<uuid>/` for unambiguous access

#### Scenario: Survey list links use UUID
- **WHEN** the survey list page renders
- **THEN** each survey link SHALL use `/surveys/<uuid>/`

### Requirement: Management command supports UUID lookup
The `export_survey` management command SHALL accept either a survey name or UUID string as the positional argument.

#### Scenario: Export by UUID
- **WHEN** user runs `python manage.py export_survey <uuid>`
- **THEN** the system SHALL export the survey matching that UUID

#### Scenario: Export by unique name
- **WHEN** user runs `python manage.py export_survey my_survey` and only one survey has that name
- **THEN** the system SHALL export that survey

#### Scenario: Export by ambiguous name
- **WHEN** user runs `python manage.py export_survey DEMO` and multiple surveys have name "DEMO"
- **THEN** the system SHALL exit with error code 1 and list matching UUIDs

### Requirement: Three-step database migration
The UUID field SHALL be introduced via a safe three-step migration sequence to handle existing data.

#### Scenario: Migration adds nullable UUID field
- **WHEN** migration 0009 runs
- **THEN** a nullable `uuid` UUIDField is added to `SurveyHeader`

#### Scenario: Data migration populates UUIDs
- **WHEN** migration 0010 runs
- **THEN** all existing SurveyHeader rows SHALL have their `uuid` field populated with unique UUID v4 values

#### Scenario: Migration finalizes UUID and removes name uniqueness
- **WHEN** migration 0011 runs
- **THEN** the `uuid` field SHALL become non-null with a unique constraint
- **AND** the `unique=True` constraint SHALL be removed from the `name` field
