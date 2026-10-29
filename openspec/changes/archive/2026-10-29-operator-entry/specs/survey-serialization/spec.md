# survey-serialization — delta for operator-entry

## ADDED Requirements

### Requirement: Audience round-trips with the structure
The structure export SHALL write `audience` on every section, group (including sub-question
groups) and question (including sub-questions) in `survey.json`. Import SHALL read a missing key as `everyone` and SHALL
report an unknown value as a warning line and read it as `everyone`.

#### Scenario: Round trip
- **WHEN** a survey with an `operators` section and a `respondents` question is exported and imported
- **THEN** the imported section and question carry the same audience values

#### Scenario: Archive from before the field
- **WHEN** an archive whose items have no `audience` key is imported
- **THEN** every item reads `everyone` and the import reports no warning

#### Scenario: Unknown value
- **WHEN** an archive carries `"audience": "staff"` on a question
- **THEN** the import succeeds, the question reads `everyone` and the report names the question

### Requirement: Responses file carries the session source
Each session in `responses.json` SHALL include `source` and `entered_by` (username or null) beside
`opened_by_kind`; import SHALL read a missing `source` as `online`.

#### Scenario: Session with source
- **WHEN** data mode is exported for a survey with a paper session
- **THEN** that session's entry reads `"source": "paper"` and the operator's username

#### Scenario: Old responses file
- **WHEN** a responses file without `source` is imported
- **THEN** its sessions read `online`
