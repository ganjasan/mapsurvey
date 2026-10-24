## 1. Scaffolding and settings

- [x] 1.1 New app `mcp/` (`apps.py`, `__init__.py`, `README.md`), in `INSTALLED_APPS`; `MCP_RESOURCE_URL` default `OAUTH_ISSUER + '/mcp'` (no trailing slash), `MCP_ALLOWED_ORIGINS`, `MCP_IMPORT_MAX_BYTES`; `api.tests.helpers.RESOURCES['mcp']` follows
- [x] 1.2 Routes: `mcp` and `mcp/` → `mcp.views.endpoint`; `.well-known/oauth-protected-resource/mcp` → `mcp.views.protected_resource_metadata`
- [x] 1.3 `api/limits.py`: group `mcp.session` (300, 600) and public `check_group(group, key)`; `survey/product_events.py`: `MCP_TOOL_CALLED`

## 2. Transport and authentication

- [x] 2.1 `mcp/protocol.py`: JSON-RPC parsing (single message and batch), error helpers, `SUPPORTED_VERSIONS`, `initialize` / `ping` / empty lists / `-32601`
- [x] 2.2 `mcp/sessions.py`: signed session id (`issue(token_id)`, `verify(value, token_id)`)
- [x] 2.3 `mcp/views.py::endpoint`: Origin check (403) → `authenticate(request, 'mcp')` (401 with the MCP `resource_metadata`, 429) → method gate (405 `Allow: POST`) → protocol-version header (400) → body → session (404) → dispatch; `Cache-Control: no-store`; notifications `202`
- [x] 2.4 `mcp/views.py::protected_resource_metadata` (resource = `MCP_RESOURCE_URL`, issuer, scopes, bearer header)
- [x] 2.5 Tests `mcp/tests/test_transport.py`, `test_auth.py`: every scenario of the first three requirements, incl. "response is never `text/event-stream`" and the byte-for-byte `resource`

## 3. Tool registry and handlers

- [x] 3.1 `mcp/tools/registry.py`: `Tool` dataclass, `args_model(base, **ids)`, `inline_refs(schema)`, `tools_for(principal)`, `get(name)`, annotations
- [x] 3.2 `mcp/tools/account.py`: `get_me`; `mcp/tools/surveys.py`: `list_surveys`, `get_survey` (sections + questions), `create_survey`, `update_survey`, `delete_survey` (confirm + `has_responses`), `publish_survey` (confirm), `close_survey`, `start_unpublished_changes`, `publish_unpublished_changes` (confirm), `discard_unpublished_changes`
- [x] 3.3 `mcp/tools/sections.py`, `mcp/tools/questions.py`: create/update/delete/reorder, `add_question` (with `parent_question_id`), `set_choices` — through `api.v1.deps`, `forms_bridge`, `out`, services with `Actor(surface='mcp')`, `strict=True`
- [x] 3.4 `mcp/tools/imports.py`: `import_survey` (size cap, in-memory ZIP, `SurveyImportJob`, `run_survey_import.delay`, `survey_import` cap), `get_import_job`
- [x] 3.5 `mcp/errors.py` + `mcp/protocol.py::call_tool`: scope → args validation (`-32602` with `fields`) → limits (`check_request`, `check_group('mcp.session')`) → handler; `ApiError` / `ServiceError` → `isError` envelope via `api.v1.errors.from_service_error`; `confirmation_required`, `has_responses`; `server_error` + capture; `{"note", "data"}` wrapping; `mcp_tool_called`
- [x] 3.6 Tests: `test_tools.py` (list filtering, hidden tool refused, structural edit → `draft_required`, Free → `pro_required` + `get_me plan`, sanitiser bytes vs editor, unknown field, IDOR), `test_destructive.py` (confirm, `has_responses` count, publish runs `screen_survey`), `test_injection.py` (note + data), `test_limits.py` (session cap, reads vs writes), `test_import.py` (job, private tier, deleted after task)

## 4. Docs, page and events

- [x] 4.1 `scripts/build_mcp_reference.py` + regenerated `help/src/content/docs/reference/mcp-tools.md` (no `draft`); `mcp/tests/test_reference.py` freshness test
- [x] 4.2 Rewrite `help/src/content/docs/how-to/use-the-mcp-server.md` (token vs OAuth, five clients, `get_me` first, injection warning, troubleshooting); drop `draft: true` and the TODO note on `connect-an-app.md`; `help_links`: `mcp`, `mcp_tools`, `connected_apps`
- [x] 4.3 Connections page: MCP block (URL, Claude Code line, OAuth note, help links); remove the notify form; `api/views.py` drops the `notify` action; translations for the new strings appended to the eleven catalogs that carry the page (`compilemessages` for them); `api/tests/test_connections.py` and `test_connected_apps.py` updated
- [x] 4.4 `survey/changelog/2026-10-24-mcp-server.html`; `mcp/README.md`; sections in `api/README.md` and `CLAUDE.md`; `docs/mcp.md` / `docs/mcp-tools.md` (untracked, main checkout) are superseded — note in the PR
- [x] 4.5 `./run_tests.sh mcp api` green (258 tests); `./run_tests.sh survey.tests.HelpSiteLinksTest survey.tests.TranslationCatalogHygieneTest survey.tests.ChangelogEntriesTest` green; `npm run build` in `help/` green (48 pages, all internal links valid)

## 5. After merge (not in this PR)

- [ ] 5.1 `scripts/oauth_reachability_check.py https://mapsurvey.org`; bot-shaped curl of `/mcp` (401 challenge) and the metadata document
- [ ] 5.2 Manual matrix in #306: Claude Code (`claude mcp add --transport http mapsurvey https://mapsurvey.org/mcp --header …`), Claude Desktop, Cursor, claude.ai connector (OAuth), ChatGPT connector (OAuth; record write-tool behaviour on an individual plan)
