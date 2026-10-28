## ADDED Requirements

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
