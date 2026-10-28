# survey-serialization Specification (delta)

## ADDED Requirements

### Requirement: A malformed archive is reported, never a server error
Import SHALL reject an archive it cannot read with an `ImportError` whose message names the problem,
so the editor renders it as a message. An archive is content from outside this installation — it can
be hand-edited, truncated, produced by an older export or by another tool — and no shape of it may
produce a 500.

The fields the import cannot invent a value for (`survey.name`, each `section.name`, each
`question.code`) SHALL be validated with a message naming the element. Every other text field SHALL
treat an explicit `null` as an absent key and fall back to its default.

#### Scenario: An explicit null where text belongs is treated as absent
- **WHEN** a `survey.json` carries `"redirect_url": null`
- **THEN** the import succeeds and the field takes its default

#### Scenario: Nulls across the section and question tree do not fail the import
- **WHEN** optional section and question text fields are explicitly null
- **THEN** each is read as absent and the import succeeds

#### Scenario: A missing required field names itself
- **WHEN** a section in the archive has no name
- **THEN** the import is rejected with a message naming the missing field

#### Scenario: A wrongly typed field is reported, not raised through
- **WHEN** a field carries a type the import does not expect
- **THEN** the archive is rejected with a readable message rather than a server error

#### Scenario: The creator sees the message
- **WHEN** a creator uploads such an archive through the editor
- **THEN** they are returned to the editor with an error message describing the problem

#### Scenario: A well-formed archive still imports
- **WHEN** a valid structure archive is imported
- **THEN** the survey is created exactly as before
