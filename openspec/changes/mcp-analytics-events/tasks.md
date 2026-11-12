## 1. Session context

- [x] 1.1 `mcp/sessions.py`: `issue(token_id, client=None, protocol_version=None)` adds `ts`, `c`, `cv`, `pv` (trimmed, strings only); `verify` returns a `Session` (nonce, issued_ms, client_name, client_version, protocol_version); old payloads verify with empty fields
- [x] 1.2 `Session.analytics_id()`: UUIDv7 from `issued_ms` + SHA-256 of the nonce; `None` without `issued_ms`
- [x] 1.3 `mcp/views.py`: keep the verified `Session` on the request (`request.mcp_session`, `None` without the header); session key stays `sid:<nonce>`

## 2. Events

- [x] 2.1 `mcp/analytics.py`: event names, `ERROR_TYPES` map, `base_properties(request, session, protocol_version)`, `tool_call(...)`, `initialize(...)`, `tools_list(...)` over `product_events.emit`
- [x] 2.2 `mcp/protocol.py`: `initialize` passes `clientInfo` and the negotiated version to `sessions.issue` and emits `$mcp_initialize`; `tools/list` emits `$mcp_tools_list`; `call_tool` measures duration, records the HTTP status of the envelope and emits `$mcp_tool_call` in the same `finally` as `mcp_tool_called`

## 3. Tests (`mcp/tests/test_analytics.py`)

- [x] 3.1 Session: client context round trip, old payload verifies, analytics id stable per session and different across sessions, UUIDv7 version bits
- [x] 3.2 `$mcp_tool_call` on success (no error type, duration, session id), on `confirmation_required` (missing_context, status), on schema failure (validation, argument string absent from every event), on `scope_missing` (permission)
- [x] 3.3 `$mcp_initialize` and `$mcp_tools_list` (names = response, tool_count), harness headers, no `$mcp_parameters`/`$mcp_response`
- [x] 3.4 Existing `mcp_tool_called` test still green; run `./run_tests.sh mcp`

## 4. Docs

- [x] 4.1 CLAUDE.md MCP paragraph: one sentence on the MCP Analytics events and the no-arguments rule
- [x] 4.2 `openspec validate mcp-analytics-events --strict`
