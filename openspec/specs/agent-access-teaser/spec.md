# agent-access-teaser Specification

## Purpose
The account page for connecting an AI agent through MCP before the MCP server ships: what it will do, and a one-click request to be told when it is ready.
## Requirements
### Requirement: Agent access page before the server exists
The system SHALL serve `GET /editor/account/mcp/` (URL name `editor_account_mcp`) to any
signed-in creator, explaining in plain words what connecting an AI agent through MCP
will do, what the agent cannot see, and that it is not available yet, with one example
prompt. The page SHALL offer a POST action "Tell me when it's ready" that records
`CreatorPreferences.agent_access_requested_at` (first request only; later requests keep
the first timestamp) and emits the `agent_access_requested` creator event; after it, the
page SHALL show that the creator will be emailed instead of the button. The page SHALL
extend the editor base and work on every viewport. Signed-out visitors SHALL be sent to
sign in.

#### Scenario: Creator reads the teaser
- **WHEN** a signed-in creator opens `/editor/account/mcp/`
- **THEN** the page describes the agent path, shows an example prompt and the "Tell me when it's ready" button

#### Scenario: Interest recorded once
- **WHEN** the creator posts the button twice
- **THEN** `agent_access_requested_at` holds the first timestamp, one `agent_access_requested` event was emitted, and the page shows the confirmation

#### Scenario: Signed out
- **WHEN** an anonymous visitor opens the URL
- **THEN** they are redirected to the login page

### Requirement: Entrances to the agent page
The account menu in both creator bases (`base.html` and `editor/editor_base.html`) SHALL
list "AI agents & MCP" with a *soon* badge linking to `/editor/account/mcp/`, and the
editor's "?" help menu SHALL list "Connect your AI agent" linking there. The start page's
third card SHALL NOT link anywhere until the server ships (owner decision 2026-10-14). The URL name and the menu entries SHALL survive the MCP
server's launch; only the badge and the page body change then.

#### Scenario: Dashboard account menu
- **WHEN** the dashboard renders for a signed-in creator
- **THEN** the account menu contains "AI agents & MCP" linking to `/editor/account/mcp/`

#### Scenario: Editor account menu and help menu
- **WHEN** a survey editor page renders
- **THEN** the account menu contains "AI agents & MCP" and the "?" menu contains "Connect your AI agent", both linking to `/editor/account/mcp/`

