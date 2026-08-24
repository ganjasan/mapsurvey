# survey-serialization Delta Specification

## ADDED Requirements

### Requirement: Section layout serialization
Section objects in `survey.json` SHALL include the `layout` key. Import SHALL accept
archives without the key (or with an unrecognized value) by falling back to
`layout = "map"`, preserving prior rendering behavior.

#### Scenario: Layout round-trips
- **WHEN** a survey whose head section has `layout = "form"` is exported and re-imported
- **THEN** the imported head section has `layout = "form"`

#### Scenario: Legacy archive defaults to map
- **WHEN** a `survey.json` produced before this change (no `layout` key) is imported
- **THEN** every imported section gets `layout = "map"`
