# agent-access-teaser Specification

## Purpose
The former MCP teaser, after changes auth-core and mcp-server: `/editor/account/mcp/` redirects to the connections page, where the "MCP server" block gives creators the endpoint URL and the client set-up (the "Tell me when it's ready" request went with the server's launch), and the account and help menus lead there.
## Requirements
### Requirement: Entrances to the agent page
The account menu in both creator bases (`base.html` and `editor/editor_base.html`) SHALL
list "API & connections" without a badge linking to `/editor/account/connections/`, and that
page SHALL open with a link "Use your AI assistant" to `/editor/surveys/start/agent/?from=connections`
above the tokens section. The editor's "?" help menu SHALL list "Connect your AI agent"
linking to `/editor/surveys/start/agent/?from=help`. The start page's third card links to the
agent page (change `agent-onboarding`). The URL name `editor_account_mcp` SHALL survive as the
redirect to the connections page.

#### Scenario: Dashboard account menu
- **WHEN** the dashboard renders for a signed-in creator
- **THEN** the account menu contains "API & connections" linking to `/editor/account/connections/` and no *soon* badge

#### Scenario: Editor account menu and help menu
- **WHEN** a survey editor page renders
- **THEN** the account menu contains "API & connections" linking to `/editor/account/connections/`, and the "?" menu contains "Connect your AI agent" linking to `/editor/surveys/start/agent/?from=help`

#### Scenario: Connections page points at the assistant
- **WHEN** a signed-in creator opens `/editor/account/connections/`
- **THEN** the page contains a link to `/editor/surveys/start/agent/?from=connections` before the tokens section

