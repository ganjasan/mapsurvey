## MODIFIED Requirements

### Requirement: Per-IP rate limiting on registration POST

The system SHALL enforce per-client-IP rate limits on the registration endpoint using two independent
counters. Submissions that pass form validation SHALL be counted against `REGISTRATION_RATE_LIMIT_HOUR`
(default 3) per hour and `REGISTRATION_RATE_LIMIT_DAY` (default 10) per day. Submissions rejected by
form validation SHALL be counted against `REGISTRATION_INVALID_LIMIT_HOUR` (default 15) per hour and
`REGISTRATION_INVALID_LIMIT_DAY` (default 50) per day. A submission that passes form validation but
fails Turnstile SHALL count against the valid-submission counters.

Both counters SHALL be checked before form processing and incremented only after validity is known.
Limits SHALL be measured against `request.cf_ip` (set by `CloudflareIPMiddleware` from
`HTTP_CF_CONNECTING_IP`, falling back to `REMOTE_ADDR`). The system SHALL fail open if the cache
backend is unreachable.

When `REGISTRATION_SPLIT_RATE_LIMIT` is `False`, the system SHALL fall back to counting every POST
against the valid-submission counters, which is the behaviour prior to this change.

#### Scenario: Failed form validation does not consume the registration budget

- **WHEN** an IP submits four registration POSTs in an hour, the first three rejected by form validation (e.g. a password failing `AUTH_PASSWORD_VALIDATORS`) and the fourth carrying valid data
- **THEN** the fourth submission SHALL NOT be rate-limited
- **AND** a `User` SHALL be created for the fourth submission

#### Scenario: Within hourly limit succeeds

- **WHEN** an IP has made fewer than `REGISTRATION_RATE_LIMIT_HOUR` validation-passing registration POSTs in the last 60 minutes
- **THEN** the request SHALL proceed to the next defense

#### Scenario: Hourly limit exceeded

- **WHEN** an IP submits a registration POST after already making `REGISTRATION_RATE_LIMIT_HOUR` validation-passing POSTs in the last 60 minutes
- **THEN** the response SHALL be HTTP 429 with a `Retry-After` header
- **AND** an `AbuseEvent` row SHALL be written with `defense='ratelimit'` and `detail='hour'`
- **AND** the event SHALL be logged to the `abuse.ratelimit` logger
- **AND** no `User` SHALL be created

#### Scenario: Daily limit exceeded

- **WHEN** an IP submits a registration POST after already making `REGISTRATION_RATE_LIMIT_DAY` validation-passing POSTs in the last 24 hours
- **THEN** the response SHALL be HTTP 429 with a `Retry-After` header
- **AND** an `AbuseEvent` row SHALL be written with `defense='ratelimit'` and `detail='day'`

#### Scenario: Invalid-attempt ceiling bounds abuse

- **WHEN** an IP submits `REGISTRATION_INVALID_LIMIT_HOUR` form-invalid registration POSTs within 60 minutes and then submits another
- **THEN** the response SHALL be HTTP 429 with a `Retry-After` header
- **AND** an `AbuseEvent` row SHALL be written with `defense='ratelimit'` and `detail='invalid_hour'`

#### Scenario: Turnstile failure counts as a valid-submission attempt

- **WHEN** an IP submits a registration POST with well-formed data and a Turnstile token that siteverify rejects
- **THEN** the valid-submission counter SHALL be incremented
- **AND** the invalid-attempt counter SHALL NOT be incremented

#### Scenario: Cache backend unreachable fails open

- **WHEN** the Redis cache backend is unreachable during a registration POST
- **THEN** the rate-limit check SHALL not block the request
- **AND** the request SHALL proceed to the next defense

#### Scenario: Kill switch restores previous behaviour

- **WHEN** `REGISTRATION_SPLIT_RATE_LIMIT` is `False` and an IP submits four form-invalid registration POSTs in an hour
- **THEN** the fourth SHALL be refused with HTTP 429

### Requirement: Defense composition order

The defenses SHALL be evaluated in a defined order: honeypot first (cheapest, silent), then the
rate-limit check (cheap, no external network call), then form validation, then Turnstile (network call
to Cloudflare). The system SHALL stop at the first defense that triggers and SHALL NOT evaluate
remaining defenses. The rate-limit *check* SHALL run before form validation so an already-limited IP is
refused without the cost of validating; the rate-limit *counter* SHALL be incremented only after form
validity is known.

#### Scenario: Honeypot triggered short-circuits the chain

- **WHEN** the registration form is submitted with both a filled honeypot and an invalid Turnstile token
- **THEN** only the honeypot defense SHALL fire (fake-success redirect)
- **AND** Turnstile siteverify SHALL NOT be called
- **AND** neither rate-limit counter SHALL be incremented

#### Scenario: Rate limit triggered short-circuits form validation and Turnstile

- **WHEN** an IP already over its limit submits a registration POST that also has an invalid Turnstile token
- **THEN** only the rate-limit defense SHALL fire (HTTP 429)
- **AND** Turnstile siteverify SHALL NOT be called

#### Scenario: Invalid form short-circuits Turnstile

- **WHEN** a registration POST with an empty honeypot, an IP under its limits, and form-invalid data is submitted
- **THEN** the form SHALL be re-rendered with errors
- **AND** Turnstile siteverify SHALL NOT be called

### Requirement: Configuration via Django settings and environment variables

All abuse-defense thresholds, keys, and feature flags SHALL be readable from environment variables and exposed through Django settings. The system SHALL ship with safe defaults for local development.

#### Scenario: Default rate-limit thresholds

- **WHEN** `REGISTRATION_RATE_LIMIT_HOUR` and `REGISTRATION_RATE_LIMIT_DAY` are not set in the environment
- **THEN** `settings.REGISTRATION_RATE_LIMIT_HOUR` SHALL be `3` and `settings.REGISTRATION_RATE_LIMIT_DAY` SHALL be `10`

#### Scenario: Default invalid-attempt thresholds

- **WHEN** `REGISTRATION_INVALID_LIMIT_HOUR` and `REGISTRATION_INVALID_LIMIT_DAY` are not set in the environment
- **THEN** `settings.REGISTRATION_INVALID_LIMIT_HOUR` SHALL be `15` and `settings.REGISTRATION_INVALID_LIMIT_DAY` SHALL be `50`

#### Scenario: Split rate limit defaults to enabled

- **WHEN** `REGISTRATION_SPLIT_RATE_LIMIT` is not set in the environment
- **THEN** `settings.REGISTRATION_SPLIT_RATE_LIMIT` SHALL be `True`

#### Scenario: Empty Turnstile secret enables dev bypass

- **WHEN** `TURNSTILE_SECRET_KEY` is unset or empty
- **THEN** Turnstile verification SHALL be skipped for all requests

#### Scenario: CLOUDFLARE_TRUSTED defaults to false

- **WHEN** `CLOUDFLARE_TRUSTED` is not set in the environment
- **THEN** `settings.CLOUDFLARE_TRUSTED` SHALL be `False`
