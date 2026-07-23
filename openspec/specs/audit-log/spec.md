## Purpose

Keep an append-only, admin-readable record of destructive and lifecycle editor operations so any data loss or state change can be reconstructed after the fact.

## Requirements

### Requirement: Destructive and lifecycle operations are audited
The system SHALL write an append-only `AuditLog` record for every destructive or lifecycle editor operation: survey trash, restore, manual purge, auto-purge, status transition, test-data clearing, draft publish, draft discard, password set/remove, and test-token regeneration.

#### Scenario: Trashing a survey writes an audit record
- **WHEN** an owner moves a survey to trash
- **THEN** an `AuditLog` row SHALL be created with action `survey_trash`, the actor user, the survey uuid and name, the client IP, and a timestamp

#### Scenario: Status transition writes an audit record
- **WHEN** an owner transitions a survey (e.g. testing → published)
- **THEN** an `AuditLog` row SHALL be created with action `status_transition` and metadata containing the old and new status

#### Scenario: Clearing test data writes an audit record
- **WHEN** an owner publishes with "clear test data" checked
- **THEN** an `AuditLog` row SHALL be created with action `clear_test_data` and metadata containing the number of deleted sessions

### Requirement: Audit records survive deletion of their target
Audit records SHALL reference the target survey by stored uuid and name (no foreign key), so purging a survey MUST NOT remove or alter its audit history.

#### Scenario: Audit history remains after purge
- **WHEN** a survey is permanently purged
- **THEN** all `AuditLog` rows referencing its uuid SHALL remain queryable with their original content

### Requirement: Audit records survive deletion of the actor
The actor reference SHALL use `SET_NULL` on user deletion so audit history is preserved without the account.

#### Scenario: Actor account deleted
- **WHEN** a user with audit records is deleted
- **THEN** their audit rows SHALL remain with `actor` set to NULL

### Requirement: Auditing never breaks the audited operation
The audit helper SHALL swallow all exceptions; a failure to write an audit record MUST NOT fail or roll back the underlying operation.

#### Scenario: Audit write fails
- **WHEN** the audit insert raises (e.g. DB hiccup)
- **THEN** the surrounding operation SHALL complete normally

### Requirement: Audit log is read-only in admin
The system SHALL expose `AuditLog` in Django admin as read-only: no add, change, or delete permitted through the admin interface.

#### Scenario: Admin cannot modify audit entries
- **WHEN** a superuser opens an `AuditLog` entry in Django admin
- **THEN** the entry SHALL be viewable but not editable or deletable
