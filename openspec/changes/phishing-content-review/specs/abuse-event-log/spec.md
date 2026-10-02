## MODIFIED Requirements

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
- **THEN** the `defense` field SHALL be one of `"captcha"`, `"ratelimit"`, `"honeypot"`, `"email_domain"` (reserved for Phase 2 use), or `"content_screen"`

#### Scenario: Detail field captures defense-specific context

- **WHEN** a captcha defense fails because of a missing token
- **THEN** the `detail` field SHALL contain `"missing_token"`
- **WHEN** a captcha defense fails because Cloudflare's siteverify returned `success=false`
- **THEN** the `detail` field SHALL contain `"siteverify_rejected"`
- **WHEN** a rate-limit defense fires
- **THEN** the `detail` field SHALL contain the violated limit identifier (e.g., `"3_per_hour"` or `"10_per_day"`)

#### Scenario: Content screening events carry ids, never identities

- **WHEN** a survey is held, released, confirmed as phishing, or reported by a respondent
- **THEN** one `AbuseEvent` row with `defense='content_screen'` SHALL be written
- **AND** `detail` SHALL start with `hold survey=<id> score=<n>`, `release survey=<id>`, `confirm survey=<id> user=<id>` or `report survey=<id>` respectively
- **AND** `detail` SHALL contain neither an email address nor a username
- **AND** `ip` MAY be null when the event is written outside a request (Celery or a decision helper)
