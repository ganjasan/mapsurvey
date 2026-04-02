## ADDED Requirements

### Requirement: Version field in serialization
The system SHALL include the `version_number` field in survey export and handle it during import.

#### Scenario: Export includes version
- **WHEN** a survey with `version_number=3` is exported
- **THEN** `survey.json` SHALL include `"version": 3`

#### Scenario: Import with version
- **WHEN** a survey archive contains `"version": 5`
- **THEN** the imported `SurveyHeader.version_number` SHALL be set to 5

#### Scenario: Import without version field
- **WHEN** a survey archive does not contain a `version` field
- **THEN** the imported `SurveyHeader.version_number` SHALL default to 1

#### Scenario: Archived versions not exported
- **WHEN** a survey is exported and has archived versions
- **THEN** only the canonical survey's structure SHALL be exported (archived versions are excluded)

#### Scenario: Import creates canonical survey
- **WHEN** a survey is imported
- **THEN** it SHALL be created as a canonical survey (`is_canonical=True`, `canonical_survey=NULL`)
