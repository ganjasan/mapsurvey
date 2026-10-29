## MODIFIED Requirements

### Requirement: Token validation order and uniform refusal
`authenticate()` SHALL refuse, with one identical `401 invalid_token` response, a token that: lacks
the `msk_` (personal) or `msa_` (OAuth access token) prefix or has an implausible length; has no
row with a matching SHA-256 checksum; has no `TokenProfile` (the toolkit's DCR registration tokens
and any token not minted by `api.tokens` or the authorization server); is expired; has
`revoked_at` set; does not list the requested audience; or belongs to a user who cannot sign in
(`email_verification.can_sign_in` is false: banned, or unconfirmed past the sign-in grace period).
Lookup SHALL be by checksum (hash) so a database read discloses no usable token. The response
body and timing SHALL not distinguish "unknown" from "revoked". A refresh token value (`msr_`)
presented as a bearer SHALL be refused before any database query. The OAuth authorization page
and the refresh-token grant SHALL apply the same `can_sign_in` rule.

#### Scenario: Revoked token
- **WHEN** a token revoked on the connections page is presented
- **THEN** the response is `401 invalid_token`, identical in body to an unknown token

#### Scenario: Expired token
- **WHEN** a token whose `expires` is in the past is presented
- **THEN** the response is `401 invalid_token`

#### Scenario: Deactivated account
- **WHEN** the token's user has `is_active = False` (phishing confirmation)
- **THEN** the next request with that token is `401 invalid_token` with no caching window

#### Scenario: Unconfirmed account past the grace period
- **WHEN** the token's user registered more than 24 hours ago and has not confirmed the address
- **THEN** the next request with that token is `401 invalid_token`

#### Scenario: Unconfirmed account within the grace period
- **WHEN** the token's user registered 2 hours ago and has not confirmed the address
- **THEN** read requests succeed, and a publish request is refused with `403 email_unconfirmed`

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
