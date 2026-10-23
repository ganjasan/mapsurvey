## MODIFIED Requirements

### Requirement: Bearer token is the only API credential
`api.auth.authenticate(request, audience)` SHALL resolve a principal only from an `Authorization: Bearer <token>` request header. A request without that header SHALL be anonymous on every API path regardless of any session cookie, and API views SHALL never read `request.user`. API views SHALL be exempt from CSRF checks because they accept no cookie credential. On `/api/v1/` the `401` challenge SHALL also name the API's RFC 9728 protected-resource metadata (`resource_metadata="<issuer>/.well-known/oauth-protected-resource/api/"`), and a request with an HTTP method the path does not offer SHALL still be answered `401 invalid_token` first when it carries no valid bearer.

#### Scenario: Signed-in browser without a bearer
- **WHEN** a client with a valid creator session cookie and no `Authorization` header requests `/api/v1/me`
- **THEN** the response is `401` with `{"error": "invalid_token"}` and a `WWW-Authenticate` header starting `Bearer realm="mapsurvey"` and carrying `resource_metadata=`

#### Scenario: Token in the query string
- **WHEN** a request carries `?access_token=msk_…` and no header
- **THEN** the response is `401 invalid_token`

#### Scenario: Cross-site form POST with cookies
- **WHEN** a signed-in browser submits an HTML form to an API path from another origin
- **THEN** the response is `401 invalid_token` and nothing is changed

#### Scenario: Wrong method with a valid bearer
- **WHEN** a valid token sends `POST /api/v1/me`
- **THEN** the response is `405 method_not_allowed` in the envelope with an `Allow` header
