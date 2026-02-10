## ADDED Requirements

### Requirement: Survey visibility field
`SurveyHeader` SHALL have a `visibility` CharField with choices: `"private"` (default), `"demo"`, `"public"`.

#### Scenario: Default visibility
- **WHEN** a new SurveyHeader is created without specifying visibility
- **THEN** its visibility SHALL be `"private"`

#### Scenario: Existing surveys remain private
- **WHEN** the migration is applied
- **THEN** all existing SurveyHeader records SHALL have visibility set to `"private"`

### Requirement: Survey archived flag
`SurveyHeader` SHALL have an `is_archived` BooleanField (default `False`).

#### Scenario: Default archived state
- **WHEN** a new SurveyHeader is created without specifying is_archived
- **THEN** is_archived SHALL be `False`

### Requirement: Survey cards on landing page
The landing page SHALL display cards for surveys whose visibility is `"demo"` or `"public"`.

#### Scenario: Only visible surveys shown
- **WHEN** the landing page is rendered and there are surveys with visibility `"private"`, `"demo"`, and `"public"`
- **THEN** only surveys with visibility `"demo"` or `"public"` SHALL appear in the cards section

#### Scenario: No visible surveys
- **WHEN** the landing page is rendered and all surveys have visibility `"private"`
- **THEN** the survey cards section SHALL be hidden entirely

### Requirement: Survey card content
Each survey card SHALL display the survey name, organization name (if set), and a status indicator.

#### Scenario: Active public survey card
- **WHEN** a survey has visibility `"public"` and is_archived is `False`
- **THEN** the card SHALL display the survey name, organization, and an "Active" status badge
- **AND** the card SHALL link to the survey at `/surveys/<name>/`

#### Scenario: Demo survey card
- **WHEN** a survey has visibility `"demo"`
- **THEN** the card SHALL display the survey name, organization, and a "Demo" status badge
- **AND** the card SHALL link to the survey at `/surveys/<name>/`

#### Scenario: Archived survey card
- **WHEN** a survey has visibility `"public"` and is_archived is `True`
- **THEN** the card SHALL display the survey name, organization, and an "Archived" status badge
- **AND** the card SHALL link to the survey's data download at `/surveys/<name>/download`

#### Scenario: Survey without organization
- **WHEN** a survey card is rendered for a survey with no organization
- **THEN** the organization line SHALL be omitted from the card

### Requirement: Survey card response count
Each survey card SHALL display the number of completed sessions.

#### Scenario: Response count display
- **WHEN** a survey card is rendered
- **THEN** it SHALL display the count of SurveySession records for that survey

### Requirement: Survey cards ordering
Survey cards SHALL be ordered: demo surveys first, then active public surveys, then archived surveys.

#### Scenario: Card ordering
- **WHEN** the landing page has demo, active, and archived surveys
- **THEN** demo surveys SHALL appear first, followed by active public surveys, followed by archived surveys
