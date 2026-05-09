## ADDED Requirements

### Requirement: Cloudflare Turnstile token validation on registration POST

The system SHALL render a Cloudflare Turnstile widget on the registration form and SHALL reject any POST to the registration endpoint whose Turnstile token cannot be verified against Cloudflare's `siteverify` endpoint, except in environments where `TURNSTILE_SECRET_KEY` is empty (in which case the check SHALL be skipped to keep local development workable).

#### Scenario: Valid token passes verification

- **WHEN** the registration form is submitted with a valid `cf-turnstile-response` token and `TURNSTILE_SECRET_KEY` is set
- **THEN** the server-side `siteverify` call SHALL return `success: true` and the request SHALL proceed to the next defense

#### Scenario: Missing token blocks the request

- **WHEN** the registration form is submitted with no `cf-turnstile-response` field and `TURNSTILE_SECRET_KEY` is set
- **THEN** the form SHALL fail validation with a "CAPTCHA verification required" error
- **AND** no `User` row SHALL be created
- **AND** no activation email SHALL be sent

#### Scenario: Invalid token blocks the request

- **WHEN** the registration form is submitted with a token that `siteverify` rejects
- **THEN** the form SHALL fail validation with a "CAPTCHA verification failed" error
- **AND** an `AbuseEvent` row SHALL be written with `defense='captcha'`
- **AND** the failure SHALL be logged to the `abuse.captcha` logger at WARNING level

#### Scenario: Local development bypass

- **WHEN** the registration form is submitted and `TURNSTILE_SECRET_KEY` is empty
- **THEN** the Turnstile check SHALL be skipped
- **AND** the request SHALL proceed to the next defense regardless of whether a token is present

#### Scenario: Cloudflare API timeout fails closed

- **WHEN** `siteverify` does not respond within 5 seconds
- **THEN** the request SHALL be rejected with the same error as an invalid token
- **AND** the failure SHALL be logged

### Requirement: Per-IP rate limiting on registration POST

The system SHALL enforce per-client-IP rate limits of `REGISTRATION_RATE_LIMIT_HOUR` (default 3) attempts per hour and `REGISTRATION_RATE_LIMIT_DAY` (default 10) attempts per day on the registration endpoint. Limits SHALL be measured against `request.cf_ip` (set by `CloudflareIPMiddleware` from `HTTP_CF_CONNECTING_IP`, falling back to `REMOTE_ADDR`). The system SHALL fail open if the cache backend is unreachable.

#### Scenario: Within hourly limit succeeds

- **WHEN** an IP has made fewer than `REGISTRATION_RATE_LIMIT_HOUR` registration POSTs in the last 60 minutes
- **THEN** the request SHALL proceed to the next defense

#### Scenario: Hourly limit exceeded

- **WHEN** an IP submits a registration POST after already making `REGISTRATION_RATE_LIMIT_HOUR` POSTs in the last 60 minutes
- **THEN** the response SHALL be HTTP 429 with a `Retry-After` header
- **AND** an `AbuseEvent` row SHALL be written with `defense='ratelimit'`
- **AND** the event SHALL be logged to the `abuse.ratelimit` logger
- **AND** no `User` SHALL be created

#### Scenario: Daily limit exceeded

- **WHEN** an IP submits a registration POST after already making `REGISTRATION_RATE_LIMIT_DAY` POSTs in the last 24 hours
- **THEN** the response SHALL be HTTP 429 with a `Retry-After` header
- **AND** an `AbuseEvent` row SHALL be written with `defense='ratelimit'`

#### Scenario: Cache backend unreachable fails open

- **WHEN** the Redis cache backend is unreachable during a registration POST
- **THEN** the rate-limit check SHALL not block the request
- **AND** the request SHALL proceed to the next defense

### Requirement: Honeypot field with silent fake-success rejection

The registration form SHALL include a hidden honeypot field named `website`. When the field is submitted with a non-empty value the system SHALL respond with the same redirect that a successful registration produces (the registration-complete page) but SHALL NOT create a `User` row and SHALL NOT send any email.

#### Scenario: Empty honeypot allows real registration

- **WHEN** the registration form is submitted with `website=""` and all other defenses pass
- **THEN** the request SHALL proceed to user creation as normal

#### Scenario: Filled honeypot returns fake success

- **WHEN** the registration form is submitted with a non-empty `website` value
- **THEN** the response SHALL be HTTP 302 redirecting to the same URL as a successful registration (`django_registration_complete`)
- **AND** no `User` SHALL be created
- **AND** no email SHALL be sent
- **AND** an `AbuseEvent` row SHALL be written with `defense='honeypot'`
- **AND** the event SHALL be logged to the `abuse.honeypot` logger

#### Scenario: Honeypot field is invisible to humans

- **WHEN** a human user views the registration form in a standard browser
- **THEN** the `website` input SHALL not be visually rendered
- **AND** the field SHALL have `tabindex="-1"` and `autocomplete="off"` so keyboard navigation and form autofill never populate it

### Requirement: Defense composition order

The three defenses SHALL be evaluated in a defined order: honeypot first (cheapest, silent), then rate limit (cheap, no external network call), then Turnstile (network call to Cloudflare). The system SHALL stop at the first defense that triggers and SHALL NOT evaluate remaining defenses.

#### Scenario: Honeypot triggered short-circuits the chain

- **WHEN** the registration form is submitted with both a filled honeypot and an invalid Turnstile token
- **THEN** only the honeypot defense SHALL fire (fake-success redirect)
- **AND** Turnstile siteverify SHALL NOT be called
- **AND** the rate-limit counter SHALL NOT be incremented

#### Scenario: Rate limit triggered short-circuits Turnstile

- **WHEN** an IP exceeds the rate limit on a request that also has an invalid Turnstile token
- **THEN** only the rate-limit defense SHALL fire (HTTP 429)
- **AND** Turnstile siteverify SHALL NOT be called

### Requirement: Cloudflare client IP detection

The system SHALL provide a `CloudflareIPMiddleware` that, when `CLOUDFLARE_TRUSTED=True`, copies the `HTTP_CF_CONNECTING_IP` header value into `request.cf_ip`. When `CLOUDFLARE_TRUSTED=False` (default for local development), the middleware SHALL set `request.cf_ip` to `REMOTE_ADDR`. The middleware SHALL NOT modify `request.META["REMOTE_ADDR"]`.

#### Scenario: Cloudflare-trusted environment uses CF-Connecting-IP

- **WHEN** `CLOUDFLARE_TRUSTED=True` and a request arrives with `CF-Connecting-IP: 5.6.7.8` and `REMOTE_ADDR: 10.0.0.1`
- **THEN** `request.cf_ip` SHALL be `"5.6.7.8"`
- **AND** `request.META["REMOTE_ADDR"]` SHALL remain `"10.0.0.1"`

#### Scenario: Untrusted environment ignores Cloudflare header

- **WHEN** `CLOUDFLARE_TRUSTED=False` and a request arrives with `CF-Connecting-IP: 5.6.7.8` and `REMOTE_ADDR: 127.0.0.1`
- **THEN** `request.cf_ip` SHALL be `"127.0.0.1"`

### Requirement: Existing registration flow remains intact for legitimate users

The change SHALL NOT alter the post-registration behavior for legitimate users. The existing `user_registered` signal handler SHALL still create a personal `Organization` and `Membership`, and the activation email SHALL still be sent in a background thread.

#### Scenario: Legitimate registration still creates personal organization

- **WHEN** a registration with empty honeypot, valid Turnstile token, and below rate limits is submitted with valid form data
- **THEN** a `User` SHALL be created with `is_active=False`
- **AND** an `Organization` SHALL be created via the existing `user_registered` signal
- **AND** a `Membership` SHALL link the user to the organization with role `owner`
- **AND** the activation email SHALL be sent in a background thread
- **AND** the response SHALL redirect to `django_registration_complete`

### Requirement: Configuration via Django settings and environment variables

All abuse-defense thresholds, keys, and feature flags SHALL be readable from environment variables and exposed through Django settings. The system SHALL ship with safe defaults for local development.

#### Scenario: Default rate-limit thresholds

- **WHEN** `REGISTRATION_RATE_LIMIT_HOUR` and `REGISTRATION_RATE_LIMIT_DAY` are not set in the environment
- **THEN** `settings.REGISTRATION_RATE_LIMIT_HOUR` SHALL be `3` and `settings.REGISTRATION_RATE_LIMIT_DAY` SHALL be `10`

#### Scenario: Empty Turnstile secret enables dev bypass

- **WHEN** `TURNSTILE_SECRET_KEY` is unset or empty
- **THEN** Turnstile verification SHALL be skipped for all requests

#### Scenario: CLOUDFLARE_TRUSTED defaults to false

- **WHEN** `CLOUDFLARE_TRUSTED` is not set in the environment
- **THEN** `settings.CLOUDFLARE_TRUSTED` SHALL be `False`
