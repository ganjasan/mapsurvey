## Why

The start page's "Connect your AI agent" card, two help pages and the connections page all promise
an MCP server that does not exist: `mcp.mapsurvey.org` does not resolve, the token page is a
teaser and nothing in the repository speaks the protocol. The authorization layer (#379), the
OAuth 2.1 server (#313) and the service layer + REST API (#380) are merged, so an MCP server is now
a thin second resource server over code that already exists — the moment to ship it is now, while
the REST contract is fresh and before #312 wires the start card to it.

Issue #306, item 4 of epic #378. Pro feature (`api`), like the REST API.

## What Changes

- New Django app `mcp/`: the Model Context Protocol server as the **second resource server** of the
  API platform, served by the same image and the same Render service at `https://mapsurvey.org/mcp`
  (no new host, no new DNS, no second Dockerfile — Python 3.12 and the shared image make the
  2026-10-14 "own service" comment obsolete).
- **Transport**: Streamable HTTP in **stateless mode** — every JSON-RPC message is one `POST`, one
  JSON response. No server-initiated SSE stream is ever opened (`GET` → `405`), so no request holds
  a gunicorn worker past its own lifetime (the 2026-09-18 blocked-thread hole). Protocol versions
  `2025-03-26`, `2025-06-18`, `2025-11-25` are negotiated at `initialize`; a request naming a
  version the server does not implement is `400` with the supported list.
- **Authentication**: `api.auth.authenticate(request, 'mcp')` on every request. No bearer ⇒ `401`
  with `WWW-Authenticate: Bearer resource_metadata="<issuer>/.well-known/oauth-protected-resource/mcp"`;
  that RFC 9728 document names the authorization server and `resource = settings.MCP_RESOURCE_URL`
  byte-for-byte (`https://mapsurvey.org/mcp`, no trailing slash). A REST-only token is refused.
  Session ids are signed, bound to the token that initialised them, and `404` under another token.
  `Origin` is validated against the configured host (`403`).
- **Tools** over `survey/services/` with `Actor(surface='mcp')`, never the REST routes and never a
  model: `get_me`, `list_surveys`, `get_survey` (whole structure in one call), `create_survey`,
  `update_survey`, `delete_survey`, `publish_survey`, `close_survey`, `start_unpublished_changes`,
  `publish_unpublished_changes`, `discard_unpublished_changes`, `create_section`,
  `update_section`, `delete_section`, `reorder_sections`, `add_question`, `update_question`,
  `delete_question`, `reorder_questions`, `set_choices`, `import_survey`, `get_import_job`.
  Argument schemas are the REST API's pydantic input schemas (allow-lists, `extra='forbid'`), so
  the two surfaces accept the same bodies and the same sanitiser runs. `tools/list` omits tools
  the token's scopes cannot use; every call checks scope → role → Pro through the same helpers as
  REST.
- **Irreversible actions** need `confirm: true`: `delete_survey` (also refused outright when the
  survey has external responses, naming the count), `publish_survey`,
  `publish_unpublished_changes`. Their scopes stay off by default on token and consent forms.
- **Prompt injection**: every tool result is `{"note": <static untrusted-text notice>, "data": …}`;
  tool descriptions are static strings in code; no tool returns respondent text.
- **Limits**: the per-token windows and daily caps of `api.limits` (reads count as reads), plus a
  per-session cap of 300 tool calls per 10 minutes. `import_survey` enqueues the same
  `SurveyImportJob` as the web and REST imports.
- **Observability**: PostHog `mcp_tool_called` (tool, outcome, token id — never arguments); errors
  are the REST envelope inside an `isError` tool result, `pro_required` carrying the upgrade URL.
- **Docs**: `mcp/README.md` (developer contract), the two help pages rewritten and taken out of
  draft (`how-to/use-the-mcp-server`, generated `reference/mcp-tools` with a freshness test),
  `connect-an-app` out of draft, `help_links` keys `mcp` and `connected_apps`, connections-page
  copy, a changelog entry, `CLAUDE.md` and `api/README.md` sections.

## Capabilities

### New Capabilities
- `mcp-server`: the protocol surface — endpoint, stateless Streamable HTTP, version negotiation,
  session ids, Origin validation, protected-resource metadata, the tool registry and its
  rules (scope/role/Pro per call, confirm on irreversible tools, untrusted-data wrapping, error
  envelope, limits, events), the import job, and the generated reference page.

### Modified Capabilities
- `api-authentication`: the MCP endpoint's `401` challenge names the MCP protected-resource
  document; audience `mcp` is now consumed by a resource (a token with audiences `["api"]` is
  refused there).
- `help-site`: the MCP and connected-apps pages leave draft status; the registry gains `mcp`,
  `mcp_tools` and `connected_apps`.
- `agent-access-teaser`: the "Tell me when it's ready" block on the connections page becomes the
  MCP connection block (server URL, client snippets); the interest counter stops being collected.

## Impact

- **Code**: new `mcp/` (`views.py`, `protocol.py`, `sessions.py`, `tools/` registry, `errors.py`,
  `README.md`, tests); `api/urls.py` or `mapsurvey/urls.py` mounting `/mcp` and
  `/.well-known/oauth-protected-resource/mcp`; `settings.py` (`MCP_RESOURCE_URL` default without
  trailing slash, `INSTALLED_APPS`, `API_RATE_LIMITS` group `mcp.session`); `api/limits.py` (one
  public helper for a named group); `survey/product_events.py` (`MCP_TOOL_CALLED`);
  `survey/help_links.py`; `api/templates/api/connections.html`.
- **Dependencies**: none. The protocol subset (JSON-RPC over one POST) is small enough to
  implement in a Django view; the official SDK is ASGI/Starlette and would bring an event loop
  into a WSGI worker for no gain.
- **Tests**: `mcp/tests/` — one module per capability of the security checklist (transport,
  auth, tools, destructive, injection, limits, import, reference freshness).
- **Docs**: `help/` (three pages), `survey/changelog/2026-10-24-mcp-server.html`, `CLAUDE.md`,
  `api/README.md`, `scripts/build_mcp_reference.py`.
- **Ops**: no migration, no new env var required (`MCP_RESOURCE_URL` keeps its override). After
  deploy: `scripts/oauth_reachability_check.py`, a bot-shaped curl of `/mcp`, and the manual client
  matrix (Claude Code, Claude Desktop, Cursor, claude.ai connector, ChatGPT connector — record
  whether ChatGPT on an individual plan executes write tools) in the issue.
