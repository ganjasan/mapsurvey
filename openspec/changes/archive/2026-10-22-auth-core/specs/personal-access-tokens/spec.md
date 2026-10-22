## ADDED Requirements

### Requirement: Personal tokens are rows of the shared token table
A personal token SHALL be an `oauth2_provider` `AccessToken` with `application = NULL`, created only through `api.tokens.mint_personal_token(user, label, scopes, audiences, organization, expires)`, plus a `TokenProfile` row with `kind = "personal"`, `label`, `audiences` (non-empty subset of `["api", "mcp"]`), optional `organization` the user is a member of, `last_used_at`, `revoked_at`, `created_by_ip`. The stored token column SHALL hold a hash; the cleartext value SHALL exist only in the minting response.

#### Scenario: Minting stores a hash
- **WHEN** `mint_personal_token()` returns value `v`
- **THEN** no row in the database contains `v`, and `authenticate()` with `v` resolves the token

#### Scenario: Organisation binding must be a membership
- **WHEN** the form posts a workspace the user is not a member of
- **THEN** the form is invalid and no token is created

### Requirement: Token value format
A personal token value SHALL be `msk_` followed by at least 40 URL-safe characters from a cryptographic random source, and SHALL be unique.

#### Scenario: Format
- **WHEN** a token is minted
- **THEN** its value matches `^msk_[A-Za-z0-9_-]{40,}$`

### Requirement: Connections page lists, creates and revokes tokens
`GET /editor/account/connections/` (URL name `editor_account_connections`, login required, editor base, every viewport) SHALL list the signed-in user's non-revoked personal tokens with label, `msk_…` plus the last four characters, scopes, audiences, workspace or "All workspaces", created, expiry and last-used times, each with a *Revoke* POST. It SHALL offer a create form with: label (required, ≤ 80 chars); scope checkboxes from the registry with `surveys:publish` and `surveys:delete` unchecked by default and `surveys:read` checked; audience checkboxes "REST API" and "MCP server" both checked; workspace select ("All workspaces" or one membership); expiry choice 90 days / 1 year / never. The page SHALL be available on Free workspaces with a note that calls need Pro.

#### Scenario: Create and show once
- **WHEN** the creator submits a valid form
- **THEN** the page re-renders once with the full value in a banner saying it will not be shown again, and a reload shows only `msk_…` + last four

#### Scenario: Revoke
- **WHEN** the creator posts *Revoke* for one of their tokens
- **THEN** `revoked_at` is set, the token disappears from the list and the next API call with it is `401`

#### Scenario: Another user's token
- **WHEN** a creator posts *Revoke* with another user's token id
- **THEN** the response is 404 and nothing changes

#### Scenario: Default scopes
- **WHEN** the form renders
- **THEN** `surveys:read` is checked and `surveys:publish`, `surveys:delete` are unchecked

### Requirement: Token lifecycle is audited and measured
Minting SHALL write `AuditLog(action="api_token_create", survey=None)` with metadata `token_id`, `label`, `scopes`, `audiences`, `expires`; revoking SHALL write `api_token_revoke` with `token_id`. The creator events `api_token_created` and `api_token_revoked` SHALL carry scopes, audiences and the expiry choice and SHALL NOT carry the label or the value.

#### Scenario: Audit on create
- **WHEN** a token is minted on the page
- **THEN** one `AuditLog` row with action `api_token_create` and the token id exists, with no token value in metadata

### Requirement: Expiry choices
"90 days" and "1 year" SHALL set `expires` accordingly; "never" SHALL set it 100 years ahead. An expired token SHALL stay listed for 30 days marked *Expired*; the management command `purge_api_tokens` (added to `reclaim.sh`, the nightly Render cron) SHALL delete tokens expired or revoked more than 30 days ago.

#### Scenario: Never expires
- **WHEN** the creator chooses "never"
- **THEN** the token validates after `now + 50 years` in a frozen-time test
