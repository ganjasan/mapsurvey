## ADDED Requirements

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
