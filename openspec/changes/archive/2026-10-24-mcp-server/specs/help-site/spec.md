## MODIFIED Requirements

### Requirement: Product links resolve to existing pages
The Django project SHALL define `HELP_SITE_URL` (default `https://help.mapsurvey.org`, empty disables help links) and a registry `survey/help_links.py` mapping keys to help-site paths; templates SHALL build help links only from the registry through the `HELP_URL` context variable. A test SHALL assert that every registry path corresponds to a page file under `help/src/content/docs/`. With the MCP server live, the registry SHALL carry `mcp` (`how-to/use-the-mcp-server/`), `mcp_tools` (`reference/mcp-tools/`) and `connected_apps` (`how-to/connect-an-app/`), and those three pages SHALL NOT be `draft: true`; `reference/mcp-tools.md` SHALL be generated from the tool registry by `scripts/build_mcp_reference.py`.

#### Scenario: Registry path exists
- **WHEN** the test suite runs
- **THEN** for every key in `HELP_LINKS` a file `help/src/content/docs/<path>.md|.mdx` or `<path>/index.md|.mdx` exists

#### Scenario: Help links disabled
- **WHEN** `HELP_SITE_URL` is empty
- **THEN** templates render no help-site links and the help menu omits "Help centre"

#### Scenario: Learn more link
- **WHEN** a signed-in creator opens the reference-layers panel in the editor
- **THEN** a "Learn more" link points to `HELP_SITE_URL` + the registry path for reference layers and opens in a new tab

#### Scenario: MCP pages are published
- **WHEN** the help site is built
- **THEN** `/how-to/use-the-mcp-server/`, `/reference/mcp-tools/` and `/how-to/connect-an-app/` are in the build (no `draft: true`) and the connections page links to the first two through `HELP_URL`
