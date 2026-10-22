## MODIFIED Requirements

### Requirement: Destructive and lifecycle operations are audited
The system SHALL write an append-only `AuditLog` record for every destructive or lifecycle editor operation: survey trash, restore, manual purge, auto-purge, status transition, test-data clearing, draft publish, draft discard, password set/remove, test-token regeneration, and — with no target survey — personal API token creation (`api_token_create`) and revocation (`api_token_revoke`).

#### Scenario: Trashing a survey writes an audit record
- **WHEN** an owner moves a survey to trash
- **THEN** an `AuditLog` row SHALL be created with action `survey_trash`, the actor user, the survey uuid and name, the client IP, and a timestamp

#### Scenario: Status transition writes an audit record
- **WHEN** an owner transitions a survey (e.g. testing → published)
- **THEN** an `AuditLog` row SHALL be created with action `status_transition` and metadata containing the old and new status

#### Scenario: Clearing test data writes an audit record
- **WHEN** an owner publishes with "clear test data" checked
- **THEN** an `AuditLog` row SHALL be created with action `clear_test_data` and metadata containing the number of deleted sessions

#### Scenario: Minting an API token writes an audit record
- **WHEN** a creator mints a personal token
- **THEN** an `AuditLog` row SHALL be created with action `api_token_create`, the actor, the client IP, empty survey fields, and metadata holding the token id, label, scopes, audiences and expiry — never the token value
