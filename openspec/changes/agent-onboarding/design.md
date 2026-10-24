## Context

- The MCP server (#306) is served at `settings.MCP_RESOURCE_URL` with OAuth 2.1 (#313: DCR, CIMD,
  `https` and loopback redirects) and personal tokens (#379). Every client we offer can sign in
  through it. A client survey run on 2026-10-24 confirmed the redirects each one uses: claude.ai
  `https://claude.ai/api/mcp/auth_callback`, Claude Code / Codex / Gemini CLI loopback on a random
  port, Cursor `http://localhost:8787/callback`, VS Code `http://127.0.0.1:33418` and
  `https://vscode.dev/redirect`. **No new redirect scheme is needed**: `cursor://` and `vscode:`
  are links the browser hands to the app, not OAuth callbacks.
- The start page (`first-survey-onboarding`, `start-cards-one-click`) has an inert third card.
  Issue #312 planned a prompt hand-off and a wait-for-survey screen.
- Audience: planners, researchers, council staff. Most have one chat assistant in a browser tab,
  few have a code editor. The mockup `agent-journey.mockup.html` in this folder is the agreed
  shape.

## Goals / Non-Goals

**Goals:**
- Each client gets the simplest path its vendor allows; a non-technical creator on Claude never sees
  a token or a URL to type.
- Nobody is left without a path: assistants that cannot connect get the wizard and Claude's free
  plan.
- The page notices the connection by itself and moves on to the first prompt.
- One registry is the only place a client is described, so the next client is one entry.

**Non-Goals:**
- Listings in the ChatGPT app directory or Claude's Connectors Directory (separate issues; they need
  vendor review and, for Claude, a Team organisation to submit from).
- An MCPB bundle, an MCP Registry entry.
- #312's "Waiting for your agent's survey…" auto-redirect and a `surface='agent'` on
  `survey_created`. The MCP server already records `creation_method`; the page points to the
  dashboard.
- Any change to the OAuth server, redirect rules, MCP server or consent page.

## Decisions

### D1 · A separate page, not a modal on the start page
`/editor/surveys/start/agent/` is a page. It can be linked from the help site, the help menu and
support with `?client=`; it survives the round-trip to another tab and back; and it keeps the start
page one-click, with no "choose, then confirm" step (#335).
*Alternative*: expand the card in place, as the first mockups of `first-survey-onboarding` did.
Rejected for the same reason #335 removed the detail block.

### D2 · The client registry is Python data, rendered once
`survey/agent_clients.py` holds a tuple of `AgentClient(slug, name, group, method, icon, tag,
help_anchor, build)` entries. `build(server_url)` returns the panel's data: install URL, command,
steps (lazy-translated strings with placeholders), notes. The view renders every panel into the page
and the script only shows and hides them. No AJAX per tile, no client list in JavaScript.
Link builders:
- Claude: `https://claude.ai/customize/connectors?modal=add-custom-connector&connectorName=Mapsurvey&connectorUrl=<quote(url, safe='')>`
- Cursor: `cursor://anysphere.cursor-deeplink/mcp/install?name=mapsurvey&config=<b64(json.dumps({"url": url}))>`
- VS Code: `vscode:mcp/install?<quote(json.dumps({"name": "mapsurvey", "type": "http", "url": url}))>`
*Alternative*: a JSON file read by JavaScript. Rejected: the strings must be in the Django
catalogs, and the tests should check the links in Python.

### D3 · Connection detection polls our own tables
`editor_survey_start_agent_status` answers from `oauth2_provider.AccessToken` joined to
`api.models.TokenProfile`: an OAuth profile of the user with `'mcp' in audiences` and `created_at >
since`, or a personal profile with `'mcp'` in audiences and `last_used_at > since`. `since` is the
server time rendered into the page (not the browser clock), so clock skew cannot hide a grant. The
answer is `{connected, client}`, with `client` from `api.oauth.grants.display_name`. Polling runs
every 3 s, pauses on `visibilitychange`, and gives up after 15 minutes. The endpoint is cheap: two
indexed lookups by user.
*Alternative*: wait for the first `tools/call`. Rejected: clients call nothing until the person asks
something, which is step 2. *Alternative*: Server-Sent Events. Rejected: no streams on gthread
workers (the 2026-09-18 lesson).

### D4 · One prompt template, prefilled links as a convenience
The prompt is one `gettext` string with `{goal}`; an empty goal uses a second string. `?q=` for
claude.ai and chatgpt.com is undocumented by both vendors, so *Copy prompt* is always there, and
links are built in the browser from the typed goal (`encodeURIComponent`), never sent to us. For
ChatGPT the prompt starts with `@Mapsurvey`, because a plugin is used only when it is called by name.

### D5 · Pro notice from the entitlement, not from a failed call
`billing.entitlements.for_organization(request.active_org).has('api')` decides the notice, as on
API & connections. The gate itself stays per request in the API (`require_pro_api`); the notice only
saves the creator from discovering it mid-chat.

### D6 · Wording
The card and page say "AI assistant", "Claude", "ChatGPT", "connect", "Allow". "MCP", "server",
"token" and "OAuth" appear only inside the panels of clients that need them (coding tools,
*Something else*, the ChatGPT "choose OAuth" step). The help pages keep the technical names.

### D7 · Tags are honest
*1 click* only where a vendor link prefills everything. *limited* for Gemini (US, personal account,
Spark tasks). *not yet* for the unsupported entry. ChatGPT gets no tag but its panel names the
plans; the plan matrix is checked on a real account before release (task 1.1). If custom servers
turn out to need Business or above, the panel says so plainly.

## Risks / Trade-offs

- [Vendors change their flows and links (ChatGPT already renamed Developer mode to Plugins)] → All
  vendor facts live in `agent_clients.py`, each with a `verified` date. A test fails when a date is
  older than 120 days, which forces a recheck.
- [`?q=` stops working] → *Copy prompt* is next to every button; nothing depends on the prefill.
- [Polling load] → One user, two indexed queries, 3 s, stops after 15 min or on a hidden tab.
  Negligible next to the editor's autosave.
- [The Claude link on phones] → The docs describe adding connectors on web and desktop only; the
  panel on a narrow viewport says "on a computer works best" until a device check says otherwise.
- [A creator connects in a workspace on Free and the agent fails] → The Pro notice before
  connecting, and `get_me` already lists which workspaces include the API.
- [Detection picks up a connection made from another tab for another reason] → Harmless: it is
  still this creator's new MCP grant.

## Migration Plan

No data change. Deploy is the template, view and help pages together. Rollback is a revert: the card
goes back to inert, and the page URL 404s.

## Open Questions

- ChatGPT plan matrix for custom servers with write tools (checked on a real account, task 1.1).
- Whether Microsoft's consumer Copilot app accepts custom MCP; until verified, the tile is
  *Microsoft Copilot Studio* only.
