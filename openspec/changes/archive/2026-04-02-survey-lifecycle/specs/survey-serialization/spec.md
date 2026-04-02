## ADDED Requirements

### Requirement: Export survey status field
The system SHALL include the `status` field in the survey object within `survey.json` when exporting.

#### Scenario: Export includes status
- **WHEN** a survey with `status=published` is exported
- **THEN** the `survey` object in `survey.json` SHALL include `"status": "published"`

#### Scenario: Export excludes password hash
- **WHEN** a survey with a password set is exported
- **THEN** the `survey` object in `survey.json` SHALL NOT include `password_hash`

#### Scenario: Export excludes test token
- **WHEN** a survey with a test token is exported
- **THEN** the `survey` object in `survey.json` SHALL NOT include `test_token`

### Requirement: Import survey defaults to draft status
The system SHALL set imported surveys to `status=draft` by default. If the archive contains a `status` field, the system SHALL use that value instead.

#### Scenario: Import without status field
- **WHEN** an archive is imported with no `status` field in survey.json
- **THEN** the created survey SHALL have `status=draft`

#### Scenario: Import with status field
- **WHEN** an archive is imported with `"status": "published"` in survey.json
- **THEN** the created survey SHALL have `status=published`

#### Scenario: Import never restores password
- **WHEN** an archive from a password-protected survey is imported
- **THEN** the imported survey SHALL have `password_hash=None` regardless of the source survey

### Requirement: Import password warning
The system SHALL emit a warning when importing a survey that was exported with password protection.

#### Scenario: Warning for password-protected export
- **WHEN** an archive contains `"has_password": true` in survey.json
- **THEN** the system SHALL output warning "Survey had password protection in export. Password not imported for security — set new password in editor."

## MODIFIED Requirements

### Requirement: ZIP archive structure
The exported ZIP SHALL contain survey definition JSON and media files.

#### Scenario: Archive contents
- **WHEN** a survey is exported
- **THEN** the ZIP SHALL contain (based on mode):
  - `survey.json`: survey definition (modes: structure, full)
  - `responses.json`: sessions and answers (modes: data, full)
  - `images/structure/`: question images (modes: structure, full)
  - `images/uploads/`: user-uploaded answer files (modes: data, full)

#### Scenario: JSON format structure
- **WHEN** a survey is exported
- **THEN** `survey.json` SHALL include:
  - `version`: format version string (e.g., "1.0")
  - `exported_at`: ISO 8601 timestamp
  - `survey`: object containing survey header fields (including `status` and `has_password` boolean) and nested sections
