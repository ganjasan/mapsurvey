## ADDED Requirements

### Requirement: Authorization server metadata
The server SHALL publish an RFC 8414 document at `/.well-known/oauth-authorization-server` on the
deployment's own origin with: `issuer` equal to `settings.OAUTH_ISSUER` (the preview's
`https://<RENDER_EXTERNAL_HOSTNAME>` when `IS_PULL_REQUEST` is true, else `SITE_URL`);
`authorization_endpoint`, `token_endpoint`, `revocation_endpoint` and `registration_endpoint` under
`<issuer>/oauth/`; `response_types_supported` exactly `["code"]`; `grant_types_supported` exactly
`["authorization_code", "refresh_token"]`; `code_challenge_methods_supported` exactly `["S256"]`;
`token_endpoint_auth_methods_supported` containing `"none"`; `scopes_supported` equal to the
registry in `api.scopes`; `client_id_metadata_document_supported: true`;
`authorization_response_iss_parameter_supported: true`. No `introspection_endpoint`, no
`jwks_uri`, no OIDC discovery document and no protected-resource document SHALL be served by this
change.

#### Scenario: Required members and the PKCE list
- **WHEN** a client GETs `/.well-known/oauth-authorization-server`
- **THEN** the JSON has the members above, `code_challenge_methods_supported == ["S256"]`, and every endpoint URL starts with the issuer

#### Scenario: Preview issues for itself
- **WHEN** `IS_PULL_REQUEST=true` and `RENDER_EXTERNAL_HOSTNAME=mapsurvey-pr-1.onrender.com` while `SITE_URL` is production
- **THEN** `issuer` and every endpoint URL use `https://mapsurvey-pr-1.onrender.com`

#### Scenario: Unmounted routes
- **WHEN** a client requests `/oauth/introspect/`, `/oauth/applications/`, `/.well-known/openid-configuration` or `/oauth/.well-known/oauth-authorization-server`
- **THEN** each answers 404

### Requirement: Authorization endpoint requires a signed-in creator and PKCE S256
`GET /oauth/authorize/` SHALL redirect an anonymous visitor to the login page with `next` set to the
authorize URL and SHALL render the consent page to a signed-in user only for a request that names a
known client, a registered `redirect_uri` (per `oauth-client-registration`), `response_type=code`,
known scopes, and a `code_challenge` with `code_challenge_method=S256`. A request without
`code_challenge`, with `code_challenge_method=plain`, with an unknown scope, or with a `state`
longer than 512 bytes SHALL be refused; a `resource` that maps to no entry of `API_RESOURCE_URLS`
SHALL be refused with `invalid_target`. A refusal for a request whose client and `redirect_uri` are
valid SHALL redirect to that URI with `error` and the unchanged `state`; a refusal for an unknown
client, an unregistered or malformed `redirect_uri`, or an oversized `state` SHALL render an error
page with no `Location` header.

#### Scenario: Anonymous visitor
- **WHEN** a visitor without a session opens a valid authorize URL
- **THEN** the response redirects to the login page and `next` is the authorize URL with its query intact

#### Scenario: Missing code_challenge
- **WHEN** a signed-in user opens an otherwise valid authorize URL without `code_challenge`
- **THEN** the response redirects to the registered `redirect_uri` with `error=invalid_request` and the request's `state`

#### Scenario: plain method
- **WHEN** the authorize URL carries `code_challenge_method=plain`
- **THEN** the request is refused with `error=invalid_request` and no code is issued

#### Scenario: Unregistered redirect URI
- **WHEN** the authorize URL names a registered client and a `redirect_uri` the client did not register
- **THEN** the response is an error page (status 400) with no `Location` header and the consent form is not rendered

#### Scenario: State too long
- **WHEN** `state` is 513 bytes
- **THEN** the response is an error page naming `invalid_request` with no `Location` header

#### Scenario: State round-trips
- **WHEN** `state` is a 512-byte string of mixed URL-unsafe characters and the user allows
- **THEN** the `state` query parameter on the redirect is byte-for-byte the value sent

#### Scenario: Unknown resource
- **WHEN** `resource=https://evil.example/` is sent with a valid request
- **THEN** the response redirects to the registered URI with `error=invalid_target` and the `state`

#### Scenario: Inactive account
- **WHEN** the signed-in user has `is_active = False`
- **THEN** the authorize request is refused and no code is issued

### Requirement: Consent page content and decision
The consent page SHALL show, in this order: the redirect host (from `redirect_uri`) or, for a CIMD
client, the host of its `client_id` URL; the client name truncated to 60 characters; the requested
scopes, with `surveys:read`, `surveys:write` and `responses:read` listed as granted and
`surveys:publish` / `surveys:delete` as switches that are OFF by default and shown only when
requested; the workspaces the grant will reach (every membership) with each plan; a note that calls
will answer `pro_required` when no reachable workspace holds the `api` feature. No `logo_uri` SHALL
be fetched or rendered. The form SHALL be CSRF-protected. *Allow* SHALL issue a code whose scope is
the requested non-dangerous scopes plus the switches the user ticked — never a scope the client did
not request. *Cancel* SHALL redirect to the registered URI with `error=access_denied` and the
unchanged `state`.

#### Scenario: Attacker-chosen name
- **WHEN** a DCR client named "Mapsurvey Official" with redirect `https://evil.example/cb` reaches consent
- **THEN** the page shows `evil.example` before and more prominently than "Mapsurvey Official"

#### Scenario: Dangerous scopes off by default
- **WHEN** the client requests `surveys:read surveys:write surveys:publish`
- **THEN** the page lists read and write as granted and shows one unchecked switch for publish, and allowing without ticking it issues a code with scope `surveys:read surveys:write`

#### Scenario: Scope cannot be added
- **WHEN** the form is posted with a ticked `surveys:delete` switch the client never requested
- **THEN** the issued scope does not contain `surveys:delete`

#### Scenario: Free workspace note
- **WHEN** none of the user's workspaces holds the `api` feature
- **THEN** the page carries the Pro note, allowing still issues a code, and the first resource call with the token is `403 pro_required`

#### Scenario: Cancel
- **WHEN** the user presses Cancel
- **THEN** the response redirects to the registered URI with `error=access_denied` and the request's `state`, and no grant row exists

### Requirement: Consent is remembered per client and scope set
The page SHALL be skipped and a code issued at once when the user holds an unrevoked refresh token
for the same client whose access token's scopes include every requested scope, or when the client
has `skip_authorization` set (first-party). A request for a scope not covered by the remembered
grant SHALL render the page again. Disconnecting the app on the connections page SHALL end the
memory.

#### Scenario: Second authorize
- **WHEN** a user who allowed `surveys:read` for a client opens an authorize URL for the same client and `surveys:read`
- **THEN** the response is the code redirect without rendering the page

#### Scenario: More scopes
- **WHEN** the same user's client asks for `surveys:read responses:read`
- **THEN** the consent page is rendered

#### Scenario: After disconnect
- **WHEN** the user disconnected the client and opens the authorize URL again
- **THEN** the consent page is rendered

### Requirement: Authorization codes
A code SHALL be single-use, expire 600 seconds after issue, and be bound to `client_id`,
`redirect_uri`, `code_challenge` and the request's `resource` list. The code redirect SHALL carry
`iss` equal to the issuer (RFC 9207). Redeeming a code a second time SHALL answer `invalid_grant`
AND revoke every access and refresh token issued from that code. A token request whose
`code_verifier` does not verify against the stored S256 challenge, whose `redirect_uri` differs from
the one bound, or whose `resource` is not within the code's SHALL be refused without issuing
tokens.

#### Scenario: iss on the redirect
- **WHEN** the user allows
- **THEN** the redirect query contains `code`, `state` and `iss=<issuer>`

#### Scenario: Verifier mismatch
- **WHEN** `/oauth/token/` is posted with the code and a `code_verifier` that does not hash to the challenge
- **THEN** the response is `400 invalid_grant` and no access token row exists for the user

#### Scenario: Code used twice
- **WHEN** the same code is posted a second time after a successful exchange
- **THEN** the second response is `400 invalid_grant`, and the access and refresh tokens from the first exchange no longer validate

#### Scenario: Resource mismatch between authorize and token
- **WHEN** the code was issued with `resource=<api url>` and the token request names `resource=<mcp url>`
- **THEN** the response is `400 invalid_target`

### Requirement: Token endpoint, token format and lifetime
`POST /oauth/token/` SHALL accept `application/x-www-form-urlencoded` and the grants
`authorization_code` and `refresh_token` only; `client_credentials`, `password` and `implicit` SHALL
be refused with `unsupported_grant_type`. A public client authenticates with `client_id` alone. The
access token SHALL be `msa_` + at least 40 URL-safe random characters, expire 3600 seconds after
issue, be stored hashed, and carry a `TokenProfile` with `kind = "oauth"`, `label` = the client name
(≤ 80), `audiences` derived from `resource` (empty list → `["api", "mcp"]`; otherwise the keys of
`API_RESOURCE_URLS` whose URL is a prefix of each indicator), `organization = NULL`. The refresh token
SHALL be `msr_`-prefixed, hashed, and rotated on every use; presenting a rotated-out refresh token
SHALL revoke the whole family and answer `invalid_grant`. The token response SHALL include `scope`.

#### Scenario: Successful exchange
- **WHEN** a valid code and verifier are posted with `client_id`
- **THEN** the response is 200 JSON with `access_token` matching `^msa_[A-Za-z0-9_-]{40,}$`, `token_type: Bearer`, `expires_in: 3600`, `refresh_token` matching `^msr_`, and `scope`

#### Scenario: Audience from resource
- **WHEN** the code was issued with `resource=<API_RESOURCE_URLS["api"]>`
- **THEN** the access token's profile has `audiences == ["api"]` and the token is accepted by `/api/v1/me` but refused by `authenticate(request, "mcp")`

#### Scenario: No resource
- **WHEN** neither authorize nor token request names a `resource`
- **THEN** the profile's audiences are `["api", "mcp"]`

#### Scenario: Refresh rotation and reuse
- **WHEN** a refresh token is used once (new pair issued) and then used again
- **THEN** the second response is `400 invalid_grant`, and neither the new access token nor the new refresh token validates afterwards

#### Scenario: Disabled grants
- **WHEN** `grant_type=client_credentials` or `grant_type=password` is posted
- **THEN** the response is `400 unsupported_grant_type`

#### Scenario: Deactivated user with a live grant
- **WHEN** the user's `is_active` becomes false after tokens were issued
- **THEN** the next call with the access token is `401 invalid_token` and the next refresh is refused

### Requirement: Revocation endpoint
`POST /oauth/revoke/` SHALL implement RFC 7009 for public clients (`token` + `client_id`, optional
`token_type_hint`), SHALL answer 200 for an unknown token, and after revoking an access token that
token SHALL fail `authenticate()`; after revoking a refresh token its access token SHALL fail too.

#### Scenario: Client disconnects
- **WHEN** a client posts its refresh token to `/oauth/revoke/` with its `client_id`
- **THEN** the response is 200 and both the refresh token and its access token are refused afterwards

### Requirement: Response headers on `/oauth/*`
Every response whose path starts with `/oauth/` SHALL carry `Cache-Control: no-store`,
`Pragma: no-cache`, `X-Frame-Options: DENY` and `Content-Security-Policy: frame-ancestors 'none'`
(the CSP only when the response has none), set by `api.middleware.OAuthResponseHeadersMiddleware`
whatever any other middleware does. `SurveyEmbedMiddleware` SHALL never see a `/oauth/` request
marked embeddable.

#### Scenario: Consent page cannot be framed
- **WHEN** the consent page is rendered with the full middleware stack
- **THEN** the response has `X-Frame-Options: DENY`, `Content-Security-Policy: frame-ancestors 'none'`, `Cache-Control: no-store` and `request.survey_frame_ancestors` was never set

#### Scenario: Token and registration responses are uncacheable
- **WHEN** `/oauth/token/` or `/oauth/register/` answers, success or error
- **THEN** the response has `Cache-Control: no-store` and `Pragma: no-cache`

### Requirement: Consent and tokens are audited and measured, values never logged
Allowing SHALL write `AuditLog(action="oauth_consent")` with `client_id`, `application_id`, `scopes`
and the audiences; the creator event `oauth_app_connected` SHALL carry `application_id`, scopes,
audiences and whether the page was skipped by memory, never the client name or any token value.
No token value, code or `client_secret` SHALL be logged or sent to PostHog; `/oauth/` is in
`API_PATH_PREFIXES` so captured errors keep path and method only.

#### Scenario: Audit on consent
- **WHEN** the user allows a client
- **THEN** one `AuditLog` row with action `oauth_consent` names the application id and scopes and contains no code or token substring

#### Scenario: Exception on the token endpoint
- **WHEN** the token view raises with a code in the body
- **THEN** the captured PostHog event contains no substring of the code or of any token
