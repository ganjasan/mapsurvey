# oauth-client-registration Specification

## Purpose
How OAuth clients come to exist and which redirect URIs they may use: open dynamic registration (RFC 7591/7592) behind a per-IP budget, client ID metadata documents through an SSRF-hardened fetcher, first-party rows in the admin, the one loopback-aware redirect rule, and the purge of registrations nobody authorised.
## Requirements
### Requirement: Redirect URI rules are one helper on every path
`api/oauth/redirects.py` SHALL be the only place that decides whether a redirect URI is
registrable and whether a requested URI matches a registered one. A registrable URI SHALL use
`https`, or `http` with host `127.0.0.1`, `[::1]` or `localhost` (loopback), with no userinfo and no
fragment; wildcards SHALL NOT be accepted. Matching SHALL be exact string comparison, except that a
loopback URI matches a registered loopback URI with the same scheme, host, path and query and any
port (RFC 8252 §7.3). The helper SHALL run at DCR registration and update, in the CIMD fetcher, in a
`pre_save` receiver on `Application` (admin, shell), and in the validator at authorize and token
time. `OAUTH2_PROVIDER["ALLOWED_REDIRECT_URI_SCHEMES"]` SHALL be `["https", "http"]` with
`oauth2_provider.E003` silenced and the reason recorded beside it, and `test_settings` SHALL assert
both and that a non-loopback `http` URI is refused on every path above.

#### Scenario: Loopback any port
- **WHEN** a client registered `http://127.0.0.1:1/callback` and `http://localhost:1/callback` requests authorize with `redirect_uri=http://localhost:53124/callback`
- **THEN** the request is accepted and the code redirect goes to port 53124

#### Scenario: Non-loopback http at registration
- **WHEN** a DCR request, a CIMD document or an admin save carries `redirect_uris: ["http://example.com/cb"]`
- **THEN** DCR answers `400 invalid_redirect_uri`, CIMD resolution fails (unknown-client page), and the admin save raises a validation error

#### Scenario: Different port on a non-loopback host
- **WHEN** a client registered `https://app.example/cb` requests `redirect_uri=https://app.example:8443/cb`
- **THEN** the request is refused with an error page and no `Location`

#### Scenario: Known callbacks register
- **WHEN** DCR requests name `https://claude.ai/api/mcp/auth_callback`, `https://chatgpt.com/connector/oauth/abc123` and `https://chatgpt.com/connector_platform_oauth_redirect`
- **THEN** each registers and later matches exactly

### Requirement: Dynamic client registration is open, rate-limited and normalised
`POST /oauth/register/` (RFC 7591) SHALL accept an anonymous JSON registration of a public
`authorization_code` client (`token_endpoint_auth_method: none`), answer 201 with `client_id`,
`registration_access_token` and `registration_client_uri`, and support RFC 7592 GET/PUT/DELETE on
`/oauth/register/<client_id>/` with that token. Before the toolkit sees the body the view SHALL:
refuse the 11th registration from one IP within an hour and the 51st within a day with
`429 {"error": "rate_limited"}` and `Retry-After` (fail-open on a cache outage); strip control
characters from `client_name`, collapse whitespace and cut it to 80 characters; drop `logo_uri`,
`client_uri`, `policy_uri` and `tos_uri`; and run the redirect rules. The registration access token
SHALL NOT authenticate against any resource server.

#### Scenario: Registration
- **WHEN** an anonymous client posts `{"client_name": "My agent", "redirect_uris": ["https://app.example/cb"], "token_endpoint_auth_method": "none", "grant_types": ["authorization_code", "refresh_token"], "response_types": ["code"]}`
- **THEN** the response is 201 with `client_id`, `registration_access_token`, `token_endpoint_auth_method: "none"`, and the stored application is public with that redirect URI

#### Scenario: Eleventh registration in an hour
- **WHEN** one IP posts an 11th valid registration within 60 minutes
- **THEN** the response is `429` with `Retry-After` and no application row is created

#### Scenario: Long name is cut
- **WHEN** `client_name` is 10 000 characters
- **THEN** the response is 201 and the stored name is 80 characters

#### Scenario: Logo is dropped
- **WHEN** the registration carries `logo_uri`
- **THEN** no request is made to it, the stored application holds no logo, and the consent page shows none

#### Scenario: Registration token on the API
- **WHEN** the `registration_access_token` is presented as a bearer to `/api/v1/me`
- **THEN** the response is `401 invalid_token`

#### Scenario: RFC 7592 update
- **WHEN** the client PUTs new metadata with its registration token
- **THEN** the application is replaced with the normalised metadata and the redirect rules apply

### Requirement: Client ID metadata documents
A `client_id` that is an `https` URL SHALL be resolved through the toolkit's CIMD support with
`api.oauth.cimd.MetadataFetcher` (a `SafeMetadataFetcher` subclass): `https` only, the host resolved
and every address required to be globally routable (private, loopback, link-local including
`169.254.169.254`, CGNAT, NAT64-embedded and reserved ranges refused), no redirects followed, 5 s
total, 16 KB cap, `client_id` in the document equal to the URL, the same name normalisation and
redirect rules as DCR; cached between 5 minutes and 24 hours per the document's `Cache-Control`;
every failure SHALL surface to the OAuth flow as the unknown-client error page (oauthlib's
`InvalidClientIdError`: code `invalid_request`, "Invalid client_id parameter value."), never a
redirect, and SHALL back off repeat fetches of that URL for 60 seconds. The document's `logo_uri`
SHALL NOT be fetched or rendered; the consent page shows the `client_id` host.

#### Scenario: Private address
- **WHEN** `client_id=https://10.0.0.5/client.json`
- **THEN** no connection is attempted and the authorize response is the unknown-client error page

#### Scenario: Host resolving to the metadata address
- **WHEN** the `client_id` host resolves to `169.254.169.254`
- **THEN** no connection is attempted and the response is the unknown-client error page

#### Scenario: http scheme
- **WHEN** `client_id=http://client.example/client.json`
- **THEN** the response is the unknown-client error page

#### Scenario: Redirecting document
- **WHEN** the document URL answers 302
- **THEN** the redirect is not followed and the fetch fails

#### Scenario: Oversized document
- **WHEN** the document is 1 MB
- **THEN** reading stops at the cap and the fetch fails

#### Scenario: Mismatching client_id
- **WHEN** the document's `client_id` differs from the URL
- **THEN** the response is the unknown-client error page

#### Scenario: Valid document
- **WHEN** a mocked fetch returns a valid document for `https://claude.ai/.well-known/client.json` with `redirect_uris: ["https://claude.ai/api/mcp/auth_callback"]`
- **THEN** the consent page renders with `claude.ai` as the client host and the flow completes

### Requirement: First-party applications
A first-party client SHALL be an `Application` row created in the admin with
`registration_source = manual`, `skip_authorization` optional, subject to the same redirect rules;
the admin SHALL list applications with registration source, created time and token counts.

#### Scenario: Skip consent
- **WHEN** a first-party application has `skip_authorization = True`
- **THEN** a valid authorize request by a signed-in user redirects with a code without rendering the page

### Requirement: Unused registrations are purged
The management command `purge_oauth_clients`, run from `reclaim.sh` nightly, SHALL delete
applications with `registration_source` DCR or CIMD created more than 30 days ago that hold no
grant, no refresh token and no access token other than their registration token; it SHALL never
delete a `manual` application or one with a live grant, and SHALL report the count.

#### Scenario: Stale registration
- **WHEN** a DCR application is 31 days old and was never authorised
- **THEN** the command deletes it and its registration token

#### Scenario: Live registration
- **WHEN** a DCR application is 31 days old and a user holds an unrevoked refresh token for it
- **THEN** the command leaves it in place

### Requirement: Unsupported grant types are ignored
The system SHALL remove from `grant_types` every value other than `authorization_code` and
`refresh_token`, provided at least one of those two remains, before the toolkit sees client
metadata (a fetched Client ID Metadata Document or a DCR / RFC 7592 body). When none remains, `grant_types`
SHALL be passed on unchanged so the toolkit refuses the client as before. The response and the
stored application SHALL reflect only the supported grant types.

#### Scenario: claude.ai's document
- **WHEN** the fetched document for `https://claude.ai/oauth/mcp-oauth-client-metadata` declares `grant_types: ["authorization_code", "refresh_token", "urn:ietf:params:oauth:grant-type:jwt-bearer"]`
- **THEN** a public authorization-code application is created for that `client_id` and the consent page renders with `claude.ai` as the client host

#### Scenario: DCR with an extension grant
- **WHEN** an anonymous client registers with `grant_types: ["authorization_code", "refresh_token", "urn:ietf:params:oauth:grant-type:jwt-bearer"]`
- **THEN** the response is 201 and the registered `grant_types` are `["authorization_code", "refresh_token"]`

#### Scenario: Nothing supported
- **WHEN** a document declares only `["client_credentials"]`
- **THEN** no application is created and the authorize response is the unknown-client error page

### Requirement: A CIMD client that can be public is registered as public
The system SHALL register a fetched Client ID Metadata Document as a public client
(`token_endpoint_auth_method` `none`) when the document's `token_endpoint_auth_methods_supported`
includes `none`, whatever its `token_endpoint_auth_method` names, and SHALL drop
`token_endpoint_auth_methods_supported` and `token_endpoint_auth_signing_alg` from it. A document
whose client cannot authenticate with `none` SHALL still be refused.

#### Scenario: ChatGPT's document
- **WHEN** the fetched document for `https://chatgpt.com/oauth/client.json` declares `token_endpoint_auth_method: "private_key_jwt"` and `token_endpoint_auth_methods_supported: ["none", "private_key_jwt"]`
- **THEN** a public authorization-code application is created for that `client_id`, the consent page renders with `chatgpt.com` as the client host, and the code exchanges for a token with PKCE and no client authentication

#### Scenario: Key-only client
- **WHEN** a document declares `token_endpoint_auth_method: "private_key_jwt"` and `token_endpoint_auth_methods_supported: ["private_key_jwt"]`
- **THEN** no application is created and the authorize response is the unknown-client error page

