## Why

`https://mapsurvey.org/mcp` is the address creators paste into an AI assistant. It appears in
letters and in the product, and people click it. A browser then gets the raw JSON
`{"error": "invalid_token", …}` — a paying customer reported it as "the link isn't working".
Issue #498.

## What Changes

- A browser-shaped request to `/mcp` or `/mcp/` — `GET`, no `Authorization` header, `Accept`
  containing `text/html` — is answered `302` to `/editor/surveys/start/agent/?from=connections`,
  the "Connect your AI agent" page (owner decision 2026-10-30). A signed-out visitor goes through
  the login page to the same address, as every editor page does.
- Every other request is unchanged: MCP clients (POST, `Accept: application/json,
  text/event-stream`, any bearer) still get the `401` naming
  `/.well-known/oauth-protected-resource/mcp`, so OAuth discovery does not break. A GET with a
  bearer keeps its `405`.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `mcp-server`: the bearer-authentication requirement gains the browser exception.

## Impact

- `mcp/views.py` (`endpoint`) — one check before the Origin and bearer steps.
- `mcp/tests/test_auth.py` — browser redirect, signed-out redirect, MCP-shaped requests unchanged.
