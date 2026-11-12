## Context

PostHog's MCP Analytics product is fed by `$mcp_*` events that the `@posthog/mcp` SDK emits from a
Node MCP server. Our MCP server (`mcp/`, change `mcp-server`, #306) is hand-written Django in
stateless mode: one POST → one JSON response, a signed `Mcp-Session-Id` and no session storage.
It already sends `mcp_tool_called` (tool, outcome, token id, kind) through
`survey.product_events.emit`, which is a no-op when PostHog is unconfigured and never raises.
The property set the MCP Analytics screens read is documented in PostHog's `models-mcp.md`
reference (`$mcp_tool_name`, `$mcp_is_error`, `$mcp_error_type`, `$mcp_duration_ms`,
`$session_id`, `$mcp_client_name`, `$mcp_client_version`, `$mcp_client_user_agent`,
`$mcp_vendor_client`, `$mcp_server_name`, `$mcp_server_version`, `$mcp_protocol_version`,
`$mcp_listed_tool_names`, `$mcp_source`).

## Goals / Non-Goals

**Goals:** the dashboard, tool-quality, harness and session screens work for our server: calls,
error rate and buckets, p50/p95 latency, clients, sessions, tool neighbours, zombie tools.

**Non-Goals:** intent clusters (`$mcp_intent` would mean asking the agent for its goal on every
call, or deriving it from arguments); `$mcp_parameters` / `$mcp_response`; `$mcp_auth_failed`
for refused bearers; replacing `mcp_tool_called`.

## Decisions

**D1. One module builds the properties (`mcp/analytics.py`).** `protocol.py` calls
`analytics.tool_call(request, session, tool, outcome, status, duration_ms)`,
`analytics.initialize(...)` and `analytics.tools_list(...)`; the module assembles the common
properties (server, protocol, client, session) and emits through `product_events.emit`, so the
"never raises, no-op without a key" rule and the `distinct_id = user pk` rule are inherited, not
re-implemented. `mcp_tool_called` keeps its own emit untouched — its consumers (the spec scenario,
existing insights) stay valid.

**D2. Client context rides in the signed session id.** `sessions.issue(token_id, client=…,
protocol_version=…)` adds `ts` (issue time, ms), `c`/`cv` (clientInfo name/version, trimmed to
64/32 chars, only when strings) and `pv` to the signed payload. `verify` returns a `Session`
(nonce, issued_ms, client name/version, protocol version); a payload from before this change
(only `t`, `n`) verifies with the extra fields empty. Signed, not encrypted: the client can read
its own name back, which is harmless. The alternative — a cache entry per session — would
contradict the stateless design (D3 of `mcp-server`) and lose the context on a cache flush.

**D3. `$session_id` is a UUIDv7 derived from the session id.** PostHog's `sessions` table expects
UUIDv7 ids (the timestamp is read from them); the 48-bit time is the session's issue time and the
remaining bits come from SHA-256 of the nonce, so every call of one session carries the same id
and two sessions never collide in practice. A request without `Mcp-Session-Id`, or with an id from
before this change (no `ts`), sends no `$session_id` rather than inventing one.

**D4. Error buckets from our codes, no free text.**

| our outcome | `$mcp_error_type` |
|---|---|
| `scope_missing`, `forbidden_role`, `pro_required` | `permission` |
| `rate_limited` | `rate_limited` |
| `invalid_arguments`, `validation`, `bad_cursor` | `validation` |
| `confirmation_required` | `missing_context` |
| `server_error` | `internal` |
| any other 4xx code | `api_4xx` |

`$mcp_error_status` is the HTTP status of the envelope (absent for `invalid_arguments`, which is a
JSON-RPC error). `$mcp_error_message` carries the error CODE, never `detail`: validation details
can echo argument values (a choice label, a name), and arguments never reach events.

**D5. Client identification.** `$mcp_client_name`/`$mcp_client_version` from the session (D2) —
on `initialize` straight from `params.clientInfo`. `$mcp_client_user_agent` is the request's
`User-Agent` (capped at 256) and `$mcp_vendor_client` the `x-anthropic-client` header (capped at
64): PostHog's harness resolver prefers the vendor header, then the Claude Code UA, then the client
name. These are creator-side clients (the token owner's agent), never respondents.

**D6. `$mcp_source = 'posthog_mcp_analytics'`.** PostHog's per-tool typed queries scope some
cuts to that value (`query-mcp-harness-breakdown` with `toolName` restricts to it). Setting a
different value would hide our events from those screens; this is our own analytics project, so
we claim the SDK's identifier for compatibility. `$mcp_server_name = 'mapsurvey'`,
`$mcp_server_version` = `SERVER_INFO['version']`, `$mcp_protocol_version` = the negotiated version
(the request's `MCP-Protocol-Version`, else the session's, else the default).

**D7. Where events fire.** `$mcp_initialize` after a successful `initialize` (not when the limit
refuses it); `$mcp_tools_list` after a successful `tools/list`, with `$mcp_listed_tool_names` (the
names the token sees) and `tool_count`; `$mcp_tool_call` in the same `finally` as
`mcp_tool_called` for every resolved tool, duration measured with `time.monotonic()` from the
start of `call_tool`. An unknown tool name emits nothing (as today).

## Risks / Trade-offs

- [Session id grows by ~100 bytes] → still far under header limits; clients treat it as opaque.
- [PostHog renames a property] → the events still land; only the screens go empty again, which
  the harness breakdown check after deploy shows.
- [`$session_id` on server events creates PostHog sessions without pageviews] → web analytics
  counts sessions from `$pageview`; MCP sessions are only visible on MCP screens.

## Migration Plan

No data migration. Session ids issued before the deploy keep working (D2); their calls simply
lack `$session_id` and client name until the client re-initialises. Rollback = revert the commit.
