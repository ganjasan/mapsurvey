## REMOVED Requirements

### Requirement: Cloudflare Turnstile token validation on registration POST
**Reason**: Switched off in production on purpose (both keys empty on the web service and the shared env group, checked 2026-10-29) and removed by owner decision (#490). The public pages that still claimed it were untrue.
**Migration**: None for users. Registration keeps the honeypot and the per-IP rate limits; what a new account can do is bounded by the email-confirmation rules of `sign-in-grace-period`. Old `AbuseEvent` rows with `defense='captcha'` stay readable.

## MODIFIED Requirements

### Requirement: Per-IP rate limiting on registration POST

The system SHALL enforce per-client-IP rate limits on the registration endpoint using two independent
counters. Submissions that pass form validation SHALL be counted against `REGISTRATION_RATE_LIMIT_HOUR`
(default 3) per hour and `REGISTRATION_RATE_LIMIT_DAY` (default 10) per day. Submissions rejected by
form validation SHALL be counted against `REGISTRATION_INVALID_LIMIT_HOUR` (default 15) per hour and
`REGISTRATION_INVALID_LIMIT_DAY` (default 50) per day.

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

#### Scenario: Cache backend unreachable fails open

- **WHEN** the Redis cache backend is unreachable during a registration POST
- **THEN** the rate-limit check SHALL not block the request
- **AND** the request SHALL proceed to the next defense

#### Scenario: Kill switch restores previous behaviour

- **WHEN** `REGISTRATION_SPLIT_RATE_LIMIT` is `False` and an IP submits four form-invalid registration POSTs in an hour
- **THEN** the fourth SHALL be refused with HTTP 429

### Requirement: Defense composition order

The defenses SHALL be evaluated in a defined order: honeypot first (cheapest, silent), then the
rate-limit check (cheap, no external network call), then form validation. No CAPTCHA or other
third-party check SHALL run on registration (Cloudflare Turnstile was removed in #490). The system SHALL stop at the first defense that triggers and SHALL NOT evaluate
remaining defenses. The rate-limit *check* SHALL run before form validation so an already-limited IP is
refused without the cost of validating; the rate-limit *counter* SHALL be incremented only after form
validity is known.

#### Scenario: Honeypot triggered short-circuits the chain

- **WHEN** the registration form is submitted with both a filled honeypot and invalid form data
- **THEN** only the honeypot defense SHALL fire (fake-success redirect)
- **AND** neither rate-limit counter SHALL be incremented

#### Scenario: Rate limit triggered short-circuits form validation

- **WHEN** an IP already over its limit submits a registration POST
- **THEN** only the rate-limit defense SHALL fire (HTTP 429)

#### Scenario: No third-party script on the registration page

- **WHEN** the registration page is rendered
- **THEN** it SHALL load no Cloudflare challenge script and render no CAPTCHA widget

### Requirement: Existing registration flow remains intact for legitimate users

A legitimate registration SHALL require the `accept_terms` confirmation (see "Age and terms confirmation on sign-up"); apart from that the change SHALL NOT alter the post-registration behavior for legitimate users. The existing `user_registered` signal handler SHALL still create a personal `Organization` and `Membership`, and the activation email SHALL still be sent in a background thread.

#### Scenario: Legitimate registration still creates personal organization

- **WHEN** a registration with empty honeypot and below rate limits is submitted with valid form data and `accept_terms` checked
- **THEN** a `User` SHALL be created with `is_active=True` and an unconfirmed `EmailVerification` (see `sign-in-grace-period`)
- **AND** an `Organization` SHALL be created via the existing `user_registered` signal
- **AND** a `Membership` SHALL link the user to the organization with role `owner`
- **AND** the activation email SHALL be sent in a background thread
- **AND** the session SHALL be signed in as the new user and the response SHALL redirect to `LOGIN_REDIRECT_URL`

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

#### Scenario: CLOUDFLARE_TRUSTED defaults to false

- **WHEN** `CLOUDFLARE_TRUSTED` is not set in the environment
- **THEN** `settings.CLOUDFLARE_TRUSTED` SHALL be `False`

### Requirement: Age and terms confirmation on sign-up

The registration form SHALL include a required checkbox field `accept_terms` labelled "I am 16 or older and accept the Terms of use", where "Terms of use" links to `/terms/`. A submission without it SHALL fail form validation with HTTP 200 and a field error, and SHALL NOT create a user. The honeypot check SHALL still run before form validation, so a bot that fills the honeypot and omits `accept_terms` SHALL still receive the fake-success redirect. Existing accounts SHALL NOT be asked to confirm. The checkbox SHALL render at its natural size to the left of its label text, on the same line.

#### Scenario: Missing confirmation is rejected

- **WHEN** a registration with valid data and an empty honeypot is submitted without `accept_terms`
- **THEN** the response SHALL be HTTP 200 with an error on `accept_terms`
- **AND** no `User` SHALL be created

#### Scenario: Honeypot still wins

- **WHEN** a registration fills the honeypot field and omits `accept_terms`
- **THEN** the response SHALL be the fake-success redirect and no `User` SHALL be created

#### Scenario: Checkbox links the Terms

- **WHEN** the registration page is rendered
- **THEN** it SHALL contain a checkbox named `accept_terms` and a link to `/terms/`

#### Scenario: Checkbox sits beside its label

- **WHEN** the registration page is rendered in a browser
- **THEN** the `accept_terms` checkbox SHALL be about 16px wide, not full width
- **AND** it SHALL be left of the label text, with their tops on the same line
