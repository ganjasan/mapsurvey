# api-authentication Specification

## Purpose
How a bearer token becomes a user: `api.auth.authenticate(request, audience)` is the only entry for every programmatic client (personal tokens, OAuth grants); bearer header only, uniform 401, account state on every call, the error envelope, and the rule that token values never reach logs.
## Requirements
### Requirement: Bearer token is the only API credential
`api.auth.authenticate(request, audience)` SHALL resolve a principal only from an `Authorization: Bearer <token>` request header. A request without that header SHALL be anonymous on every API path regardless of any session cookie, and API views SHALL never read `request.user`. API views SHALL be exempt from CSRF checks because they accept no cookie credential.

#### Scenario: Signed-in browser without a bearer
- **WHEN** a client with a valid creator session cookie and no `Authorization` header requests `/api/v1/me`
- **THEN** the response is `401` with `{"error": "invalid_token"}` and `WWW-Authenticate: Bearer realm="mapsurvey"`

#### Scenario: Token in the query string
- **WHEN** a request carries `?access_token=msk_…` and no header
- **THEN** the response is `401 invalid_token`

#### Scenario: Cross-site form POST with cookies
- **WHEN** a signed-in browser submits an HTML form to an API path from another origin
- **THEN** the response is `401 invalid_token` and nothing is changed

### Requirement: Token validation order and uniform refusal
`authenticate()` SHALL refuse, with one identical `401 invalid_token` response, a token that: lacks
the `msk_` (personal) or `msa_` (OAuth access token) prefix or has an implausible length; has no
row with a matching SHA-256 checksum; has no `TokenProfile` (the toolkit's DCR registration tokens
and any token not minted by `api.tokens` or the authorization server); is expired; has
`revoked_at` set; does not list the requested audience; or belongs to a user whose `is_active` is
false. Lookup SHALL be by checksum (hash) so a database read discloses no usable token. The response
body and timing SHALL not distinguish "unknown" from "revoked". A refresh token value (`msr_`)
presented as a bearer SHALL be refused before any database query.

#### Scenario: Revoked token
- **WHEN** a token revoked on the connections page is presented
- **THEN** the response is `401 invalid_token`, identical in body to an unknown token

#### Scenario: Expired token
- **WHEN** a token whose `expires` is in the past is presented
- **THEN** the response is `401 invalid_token`

#### Scenario: Deactivated account
- **WHEN** the token's user has `is_active = False` (phishing confirmation, or never activated)
- **THEN** the next request with that token is `401 invalid_token` with no caching window

#### Scenario: Wrong audience
- **WHEN** a token whose audiences are `["mcp"]` is presented to `/api/v1/me`
- **THEN** the response is `401 invalid_token`

#### Scenario: Oversized or malformed values
- **WHEN** the bearer value is 10 000 characters, or lacks both prefixes, or is empty
- **THEN** the response is `401 invalid_token` and no database query for a token row is made

#### Scenario: OAuth access token
- **WHEN** a valid `msa_` token issued by `/oauth/token/` with audience `api` is presented to `/api/v1/me`
- **THEN** the view receives `request.principal` with `kind == "oauth"` and the token's scopes

#### Scenario: Refresh token as bearer
- **WHEN** an `msr_` value is presented as a bearer
- **THEN** the response is `401 invalid_token` and no token row is queried

#### Scenario: Registration token as bearer
- **WHEN** a DCR `registration_access_token` is presented to `/api/v1/me`
- **THEN** the response is `401 invalid_token`

### Requirement: Principal
A successful `authenticate()` SHALL return a `Principal` holding the user, the token's scopes as a frozen set, the bound organisation or `None`, the token id and the token kind (`personal` or `oauth`). `@api_endpoint(audience, scopes)` SHALL attach it as `request.principal`, then run the rate-limit check, then the view.

#### Scenario: Valid personal token
- **WHEN** a valid `msk_` token with scopes `surveys:read` is presented to `/api/v1/me`
- **THEN** the view receives `request.principal` with that user, `{"surveys:read"}`, `kind == "personal"`

### Requirement: Last use is recorded sparingly
`authenticate()` SHALL update the token's `last_used_at` only when the stored value is null or older than 60 seconds, with `update_fields`, and SHALL emit the `api_token_first_use` creator event exactly once, when the value goes from null to set.

#### Scenario: Burst of calls
- **WHEN** a token makes 100 calls within 10 seconds
- **THEN** `last_used_at` is written once and `api_token_first_use` is emitted once

### Requirement: API responses are uncacheable and carry the envelope
Every response produced through `@api_endpoint` SHALL carry `Cache-Control: no-store`. Every error SHALL be JSON `{"error": "<code>", "detail": "<text>", ...}` with a stable code: `invalid_token` (401), `scope_missing` (403), `pro_required` (403), `not_found` (404), `rate_limited` (429), `server_error` (500). A `500` SHALL contain no traceback or model name.

#### Scenario: Unhandled exception in a view
- **WHEN** an API view raises
- **THEN** the response is `500 {"error": "server_error"}` with `Cache-Control: no-store`

### Requirement: Token values never reach logs or error capture
No code path SHALL log, store or send to PostHog the bearer value: PostHog server-side error capture SHALL scrub request headers and, for paths under `/api/` and `/mcp/`, keep only path and status; `AuditLog` and `AbuseEvent` metadata SHALL hold token ids only.

#### Scenario: Exception captured with a bearer present
- **WHEN** an API view raises while the request carries `Authorization: Bearer msk_…`
- **THEN** the captured PostHog event contains no substring of the token value and no `Authorization` tag

