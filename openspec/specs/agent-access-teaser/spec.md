# agent-access-teaser Specification

## Purpose
The former MCP teaser, after changes auth-core and mcp-server: `/editor/account/mcp/` redirects to the connections page, where the "MCP server" block gives creators the endpoint URL and the client set-up (the "Tell me when it's ready" request went with the server's launch), and the account and help menus lead there.
## Requirements
### Requirement: Agent access page before the server exists
The system SHALL serve `GET /editor/account/mcp/` (URL name `editor_account_mcp`) to any
signed-in creator as a permanent redirect to `/editor/account/connections/` (URL name
`editor_account_connections`, change `auth-core`). With the MCP server live (change `mcp-server`),
the connections page SHALL keep, below the personal-tokens and connected-apps sections, an
"MCP server" block that shows the endpoint URL (`settings.MCP_RESOURCE_URL`), a Claude Code
command using a personal token, says that claude.ai and ChatGPT connect by signing in (no token),
states that the agent sees only the creator's surveys and that publishing and deleting ask for
confirmation, and links to the two help pages through `HELP_URL`. The "Tell me when it's ready"
action and the `agent_access_requested` event SHALL no longer exist; `agent_access_requested_at`
keeps its historical values. The page SHALL extend the editor base and work on every viewport.
Signed-out visitors SHALL be sent to sign in.

#### Scenario: Old URL redirects
- **WHEN** a signed-in creator opens `/editor/account/mcp/`
- **THEN** they are redirected to `/editor/account/connections/`

#### Scenario: Creator reads the MCP block
- **WHEN** a signed-in creator opens `/editor/account/connections/`
- **THEN** the page shows the tokens section and, below it, the MCP block with the endpoint URL and a `claude mcp add --transport http` command, and no "Tell me when it's ready" button

#### Scenario: Notify action retired
- **WHEN** a creator POSTs `action=notify` to the connections page
- **THEN** the page redirects to itself and no `agent_access_requested` event is emitted

#### Scenario: Signed out
- **WHEN** an anonymous visitor opens either URL
- **THEN** they are redirected to the login page

### Requirement: Entrances to the agent page
The account menu in both creator bases (`base.html` and `editor/editor_base.html`) SHALL
list "API & connections" without a badge linking to `/editor/account/connections/`, and the
editor's "?" help menu SHALL list "Connect your AI agent" linking there. The start page's
third card is wired by change #312, not this one. The URL name `editor_account_mcp` SHALL survive
as the redirect.

#### Scenario: Dashboard account menu
- **WHEN** the dashboard renders for a signed-in creator
- **THEN** the account menu contains "API & connections" linking to `/editor/account/connections/` and no *soon* badge

#### Scenario: Editor account menu and help menu
- **WHEN** a survey editor page renders
- **THEN** the account menu contains "API & connections" and the "?" menu contains "Connect your AI agent", both linking to `/editor/account/connections/`

