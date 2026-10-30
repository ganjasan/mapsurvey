## Context

`mcp.views.endpoint` refuses anything without a bearer with the `invalid_token` envelope. That is
right for MCP clients, whose OAuth discovery starts from that `401`, and wrong for a person who
clicked the address in a letter.

## Decisions

**D1 — What counts as a browser.** `GET`, no `Authorization` header, and `text/html` in `Accept`.
All three, so the rule cannot catch a client: MCP clients POST, and the Streamable HTTP GET probe a
client may send carries `Accept: text/event-stream`. A browser navigation always sends
`text/html`. A GET with a bearer is a client by definition and keeps its `405`.

**D2 — Redirect, not a page of our own.** The "Connect your AI agent" page already explains where
the address goes and walks through each assistant; a second explanation would drift. `302` (not
`301`) so a browser never caches it for an address that is also an API endpoint. The target is
`reverse('editor_survey_start_agent') + '?from=connections'`; `from=connections` is an allowed
origin there, so the back link goes to Connections.

**D3 — First check.** The browser test runs before the Origin check. A top-level navigation sends
no `Origin` on GET, and a browser GET never reaches a tool, so nothing the Origin check protects is
exposed. Signed-out visitors are handled by the target page's own `login_required`, which keeps
`next`.

## Risks

- A client that GETs with `Accept: text/html` and no bearer would be redirected instead of getting
  the `401`. None of the supported clients does; the probe is POST `initialize`.
