## MODIFIED Requirements

### Requirement: Bearer authentication with RFC 9728 discovery
Every request to the endpoint SHALL be authenticated with `api.auth.authenticate(request, 'mcp')`
before its body is read. A request without a bearer, or with a bearer that is invalid or whose
audiences lack `mcp`, SHALL be `401` with
`WWW-Authenticate: Bearer realm="mapsurvey", resource_metadata="<OAUTH_ISSUER>/.well-known/oauth-protected-resource/mcp"`
and the `invalid_token` envelope. The one exception is a browser opening the address: a `GET`
with no `Authorization` header whose `Accept` contains `text/html` SHALL be `302` to
`/editor/surveys/start/agent/?from=connections`, the page that explains how to connect an AI
assistant; every other request without a bearer keeps the `401`. The system SHALL serve that
RFC 9728 document without
authentication with `resource` equal to `settings.MCP_RESOURCE_URL` byte-for-byte,
`authorization_servers = [OAUTH_ISSUER]`, `scopes_supported` = the scopes registry and
`bearer_methods_supported = ["header"]`. The server SHALL never forward the bearer or any credential
to another service. A request whose `Origin` header is present and is not the issuer's origin (or
one of `settings.MCP_ALLOWED_ORIGINS`) SHALL be `403`.

#### Scenario: No bearer
- **WHEN** `initialize` is POSTed without an `Authorization` header
- **THEN** the response is `401 invalid_token` and `WWW-Authenticate` contains `resource_metadata="https://testserver/.well-known/oauth-protected-resource/mcp"`

#### Scenario: Address opened in a browser
- **WHEN** `/mcp` or `/mcp/` is fetched with `GET`, `Accept: text/html,…` and no `Authorization` header
- **THEN** the response is `302` to `/editor/surveys/start/agent/?from=connections`, and a signed-out visitor is then sent through login to that page

#### Scenario: Client-shaped GET keeps the 401
- **WHEN** `/mcp` is fetched with `GET`, `Accept: application/json, text/event-stream` and no `Authorization` header
- **THEN** the response is `401 invalid_token` with the same `WWW-Authenticate` as a POST

#### Scenario: Metadata document
- **WHEN** `/.well-known/oauth-protected-resource/mcp` is fetched anonymously
- **THEN** `resource` equals `settings.MCP_RESOURCE_URL`, which by default ends in `/mcp` without a trailing slash

#### Scenario: REST-only token
- **WHEN** a personal token with audiences `["api"]` POSTs `tools/list`
- **THEN** the response is `401 invalid_token`

#### Scenario: Forged Origin
- **WHEN** a valid token POSTs with `Origin: https://evil.example`
- **THEN** the response is `403` and no tool runs
