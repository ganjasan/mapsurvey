## ADDED Requirements

### Requirement: Assistant set-up guides follow the agent page
`how-to/use-the-mcp-server.md` SHALL give, per client offered on the agent page
(`agent-connect-page`), the same path the page gives, under a heading per client, with Claude and
ChatGPT first. Claude Desktop SHALL be covered by the Claude connector (one connector serves web,
desktop and phone) and the page SHALL NOT tell readers to put a remote `url` into
`claude_desktop_config.json`. ChatGPT SHALL be described through its current custom-server flow,
with the plans that can add a server. `how-to/connect-an-app.md` SHALL link to those sections
rather than repeat them. `how-to/choose-how-to-start.md` SHALL describe *Use your AI assistant* as
the third way to start. Product links SHALL reach these pages through the `HELP_URL` registry.

#### Scenario: No Desktop config with a URL
- **WHEN** the help site is built
- **THEN** no page under `help/src/content/docs/` contains a `claude_desktop_config.json` example with a `"url"` key

#### Scenario: Every page client has a section
- **WHEN** the test suite runs
- **THEN** every client slug in the agent page registry with a help anchor resolves to a heading in `how-to/use-the-mcp-server.md`

#### Scenario: Third way to start
- **WHEN** a reader opens `/how-to/choose-how-to-start/`
- **THEN** it describes *Use your AI assistant* and links to the MCP guide
