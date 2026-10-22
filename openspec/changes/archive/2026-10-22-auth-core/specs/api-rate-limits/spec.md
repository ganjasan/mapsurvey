## ADDED Requirements

### Requirement: Per-token windows and daily cap
`@api_endpoint` SHALL apply, after authentication and keyed by the token id (never by IP or user): `api.read` 600 per minute for `GET`/`HEAD`/`OPTIONS`, `api.write` 60 per minute for other methods, and `api.day` 5 000 per day for all. Exceeding any SHALL answer `429 {"error": "rate_limited", "limit": "<group>", "retry_after": <seconds>}` with a `Retry-After` header and SHALL not run the view. Limits SHALL be constants in `api/limits.py` overridable by `settings.API_RATE_LIMITS`.

#### Scenario: Write window
- **WHEN** a token makes 61 `POST` calls within a minute
- **THEN** the 61st is `429 rate_limited` with `limit == "api.write"` and `Retry-After` ≤ 60

#### Scenario: Independent budgets behind one IP
- **WHEN** two tokens from the same client IP each make 50 `POST` calls in a minute
- **THEN** all 100 succeed

#### Scenario: Reads do not consume the write window
- **WHEN** a token makes 500 `GET` and 10 `POST` calls in a minute
- **THEN** none is `429`

### Requirement: Named daily caps for expensive actions
`limits.hit(principal, action)` SHALL enforce a registry of daily caps per token — `survey_create` 50, `survey_delete` 20, `survey_import` 20, `export` 100 — raising `429 rate_limited` with `limit == action` when exceeded, and `KeyError` for an unregistered action name.

#### Scenario: 51st survey in a day
- **WHEN** `hit(principal, "survey_create")` is called the 51st time in 24 hours
- **THEN** it raises `ApiError(429)` with `limit == "survey_create"`

#### Scenario: Unregistered action
- **WHEN** `hit(principal, "surveys_frobnicate")` is called
- **THEN** it raises `KeyError`

### Requirement: Failed bearer attempts are limited per client IP
`authenticate()` SHALL count each `401 invalid_token` against the client IP (`REMOTE_ADDR` after `CloudflareIPMiddleware`) in group `api.auth_fail`, 30 per minute, and SHALL answer `429 rate_limited` before any token lookup once the count is exceeded. Successful authentications SHALL not count.

#### Scenario: Token guessing
- **WHEN** 31 requests with random bearer values arrive from one IP within a minute
- **THEN** the 31st is `429` and performed no checksum lookup

#### Scenario: Valid traffic unaffected
- **WHEN** a valid token makes 100 calls from an IP that also produced 5 failures
- **THEN** all 100 succeed

### Requirement: Fail-open on cache outage
When the rate-limit backend is unavailable, `@api_endpoint` SHALL let the request through (`RATELIMIT_FAIL_OPEN`), log a warning once per process, and the Pro gate and rights checks SHALL still apply.

#### Scenario: Redis down
- **WHEN** the cache raises during the limit check
- **THEN** the request proceeds and one warning is logged
