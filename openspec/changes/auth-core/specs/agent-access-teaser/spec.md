## MODIFIED Requirements

### Requirement: Agent access page before the server exists
The system SHALL serve `GET /editor/account/mcp/` (URL name `editor_account_mcp`) to any
signed-in creator as a permanent redirect to `/editor/account/connections/` (URL name
`editor_account_connections`, change `auth-core`). The connections page SHALL keep, below the
personal-tokens section, an "MCP server" block explaining in plain words what connecting an AI
agent through MCP will do, what the agent cannot see, and that the server is not available yet,
with one example prompt. The block SHALL offer a POST action "Tell me when it's ready" that
records `CreatorPreferences.agent_access_requested_at` (first request only; later requests keep
the first timestamp) and emits the `agent_access_requested` creator event; after it, the block
SHALL show that the creator will be emailed instead of the button. The page SHALL extend the
editor base and work on every viewport. Signed-out visitors SHALL be sent to sign in.

#### Scenario: Old URL redirects
- **WHEN** a signed-in creator opens `/editor/account/mcp/`
- **THEN** they are redirected to `/editor/account/connections/`

#### Scenario: Creator reads the MCP block
- **WHEN** a signed-in creator opens `/editor/account/connections/`
- **THEN** the page shows the tokens section and, below it, the MCP block with an example prompt and the "Tell me when it's ready" button

#### Scenario: Interest recorded once
- **WHEN** the creator posts the button twice
- **THEN** `agent_access_requested_at` holds the first timestamp, one `agent_access_requested` event was emitted, and the block shows the confirmation

#### Scenario: Signed out
- **WHEN** an anonymous visitor opens either URL
- **THEN** they are redirected to the login page

### Requirement: Entrances to the agent page
The account menu in both creator bases (`base.html` and `editor/editor_base.html`) SHALL
list "API & connections" without a badge linking to `/editor/account/connections/`, and the
editor's "?" help menu SHALL list "Connect your AI agent" linking there. The start page's
third card SHALL NOT link anywhere until the MCP server ships (owner decision 2026-10-14). The
URL name `editor_account_mcp` SHALL survive as the redirect.

#### Scenario: Dashboard account menu
- **WHEN** the dashboard renders for a signed-in creator
- **THEN** the account menu contains "API & connections" linking to `/editor/account/connections/` and no *soon* badge

#### Scenario: Editor account menu and help menu
- **WHEN** a survey editor page renders
- **THEN** the account menu contains "API & connections" and the "?" menu contains "Connect your AI agent", both linking to `/editor/account/connections/`
