## ADDED Requirements

### Requirement: AbuseEvent persistence model

The system SHALL provide an `AbuseEvent` Django model that records every triggered abuse defense. The model SHALL store at minimum the defense identifier, the client IP that triggered it, the user-agent string, free-form detail, and a creation timestamp.

#### Scenario: Triggered defense writes one row

- **WHEN** any abuse defense (captcha, ratelimit, honeypot) blocks a request
- **THEN** exactly one `AbuseEvent` row SHALL be created
- **AND** the `defense` field SHALL contain the slug of the triggering defense
- **AND** the `ip` field SHALL contain the client IP (from `request.cf_ip`)
- **AND** the `user_agent` field SHALL contain the request's `User-Agent` header
- **AND** the `created_at` field SHALL be set to the current time

#### Scenario: Defense slug is constrained to known values

- **WHEN** `AbuseEvent` is created
- **THEN** the `defense` field SHALL be one of `"captcha"`, `"ratelimit"`, `"honeypot"`, or `"email_domain"` (the last reserved for Phase 2 use)

#### Scenario: Detail field captures defense-specific context

- **WHEN** a captcha defense fails because of a missing token
- **THEN** the `detail` field SHALL contain `"missing_token"`
- **WHEN** a captcha defense fails because Cloudflare's siteverify returned `success=false`
- **THEN** the `detail` field SHALL contain `"siteverify_rejected"`
- **WHEN** a rate-limit defense fires
- **THEN** the `detail` field SHALL contain the violated limit identifier (e.g., `"3_per_hour"` or `"10_per_day"`)

### Requirement: Indexed for analytical queries

The `AbuseEvent` model SHALL index `defense` and `created_at` columns to support analytical queries (counts per defense per time window) without full-table scans, in preparation for the Phase 3 anomaly dashboard.

#### Scenario: Defense filter is indexed

- **WHEN** a query filters on `AbuseEvent.objects.filter(defense='honeypot')`
- **THEN** the database SHALL use the `defense` column index

#### Scenario: Time-window filter is indexed

- **WHEN** a query filters on `created_at__gte=<timestamp>`
- **THEN** the database SHALL use the `created_at` column index

### Requirement: log_abuse_event helper

The system SHALL provide a `survey.abuse.log_abuse_event(defense: str, request, detail: str)` helper that creates one `AbuseEvent` row and emits one log line through the matching `abuse.<defense>` Python logger.

#### Scenario: Helper creates row and log line

- **WHEN** `log_abuse_event("honeypot", request, "filled")` is called
- **THEN** one `AbuseEvent` row SHALL be created with `defense="honeypot"` and `detail="filled"`
- **AND** one log line SHALL be emitted on the `abuse.honeypot` logger at WARNING level
- **AND** the log line SHALL include the IP and the detail string

#### Scenario: Helper is the single write path

- **WHEN** any defense triggers
- **THEN** the defense's code SHALL call `log_abuse_event()` exactly once
- **AND** no other code path SHALL write `AbuseEvent` rows

### Requirement: No PII beyond IP and user-agent

The `AbuseEvent` model SHALL NOT persist email addresses, attempted usernames, or other personally identifying form data beyond the request IP and user-agent. Such data is operationally useful but creates a GDPR retention concern that is out of scope for this change.

#### Scenario: Email is not persisted in detail

- **WHEN** a honeypot or rate-limit defense fires on a registration POST that included an email
- **THEN** the email value SHALL NOT appear in any `AbuseEvent` field
- **AND** the email value MAY appear in the operational log line for short-lived diagnostic use, but SHALL NOT be persisted to the database
