## Why

PostHog's MCP Analytics screens (dashboard, tool quality, harness breakdown, sessions) read only
`$mcp_tool_call`, `$mcp_initialize` and `$mcp_tools_list` with `$mcp_*` properties — the format
the `@posthog/mcp` SDK emits. Our server is hand-written Django (the SDK is Node-only), so it sends
only `mcp_tool_called`, and every MCP Analytics screen is empty although the calls reach PostHog
(#649). We cannot see error rates by tool, latency, which clients connect, or which tools are
offered but never called.

## What Changes

- Every `tools/call` also emits `$mcp_tool_call` with the tool name, error flag, error bucket and
  HTTP status, duration, session id, client name/version, user agent, vendor client header, server
  name/version and protocol version. `mcp_tool_called` stays exactly as it is.
- `initialize` emits `$mcp_initialize`; `tools/list` emits `$mcp_tools_list` with the advertised
  tool names.
- The signed `Mcp-Session-Id` additionally carries the issue time, the client's `clientInfo`
  (name, version, capped) and the negotiated protocol version, so later stateless requests can
  report them. Session ids issued before the deploy keep verifying.
- Never sent: `$mcp_parameters`, `$mcp_response`, `$mcp_intent`, or any free-text error message
  — the "arguments never reach events" rule of `mcp-server` holds for the new events too.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `mcp-server`: the observability requirement gains the MCP Analytics events and their property
  set, and the session-id requirement gains the client context it carries.

## Impact

- Code: `mcp/protocol.py` (emission at initialize / tools/list / tools/call), `mcp/sessions.py`
  (payload with issue time and client context), `mcp/views.py` (passes the verified session to
  dispatch), new `mcp/analytics.py` (property building, error-type map).
- PostHog: three new event names in project 248938; no schema or dashboard work on our side.
- No migration, no settings, no dependency.
