## 1. Facts before copy

- [ ] 1.1 Check on real accounts and record in `agent_clients.py` with the date: ChatGPT custom-server flow names and which plans can add a server with write tools; the claude.ai add-connector link on desktop and on a phone; Cursor and VS Code install links open with the URL filled in
- [x] 1.2 Check Le Chat, Perplexity, Copilot Studio, Windsurf and Gemini CLI/Antigravity steps against their current docs; decide the Gemini and Microsoft Copilot tile wording (design, Open Questions)

## 2. Client registry

- [x] 2.1 `survey/agent_clients.py`: `AgentClient` entries for every client in the spec, groups, methods, tags, help anchors, `verified` dates, `build(server_url)` returning install URL / command / steps
- [x] 2.2 Link builders for Claude, Cursor (base64 JSON) and VS Code (encoded JSON), all from `settings.MCP_RESOURCE_URL`
- [x] 2.3 Tests: one tile per entry and chat group first; Cursor `config` decodes to `{"url": MCP_RESOURCE_URL}`; Claude link carries name and encoded URL; no built string contains `mapsurvey.org` when the setting points elsewhere; `verified` older than 120 days fails

## 3. Page and status endpoint

- [x] 3.1 Views `editor_survey_start_agent` (GET, editor role) and `editor_survey_start_agent_status` (GET, JSON, signed-in user only) and their URLs
- [x] 3.2 Status query over `AccessToken` + `TokenProfile` (OAuth with `mcp` audience created after `since`, or personal with `mcp` audience used after `since`); `client` from `grants.display_name`; server-rendered `since`
- [x] 3.3 Template `editor/survey_start_agent.html`: stepper, tiles in two groups, one panel per client, Pro notice from the `api` entitlement, *I've connected*, prompt step, dashboard pointer; mobile layout
- [x] 3.4 `survey/assets/js/survey_start_agent.js`: tile switching with `?client=` and the remembered choice (try/catch around `localStorage`), status polling (3 s, pause on hidden tab, stop at 15 min), prompt building and `?q=` links in the browser, copy buttons, *Tell us which*
- [x] 3.5 Unsupported panel: wizard link only when a provider is configured, *Use Claude* selects the Claude tile, *Tell us which* posts the name (truncated to 40) as an event
- [x] 3.6 Tests (GIVEN/WHEN/THEN): editor sees the page; viewer refused; anonymous redirected; POST 405; `?client=chatgpt` selects ChatGPT; unknown client falls back; Pro notice on Free only; status false for older grants, true after a new OAuth grant, true after a personal token's MCP use, false for another user's grant; no token or scope in the status JSON

## 4. Start page card

- [x] 4.1 `survey_start.html`: third card becomes a link to the agent page, *Use your AI assistant*, label "Your assistant", "New" badge, Claude and ChatGPT named; remove `.soon` styles, ribbon and `aria-disabled`; update the template comment
- [x] 4.2 Update the start-page tests to the modified `survey-start-chooser` scenarios (live card, link, no "MCP"/"token")

## 5. Events

- [x] 5.1 `product_events.py`: `agent_client_chosen`, `agent_install_clicked`, `agent_connected`, `agent_prompt_opened`, `agent_client_requested`; browser events guarded by `window.posthog`, the request event server-side
- [x] 5.2 Test that no event property carries the goal, the prompt or a URL with `q=`

## 6. Help centre and changelog

- [x] 6.1 Rewrite `help/src/content/docs/how-to/use-the-mcp-server.md` per client in the page's order; Claude Desktop through the connector; ChatGPT current flow and plans
- [x] 6.2 `how-to/connect-an-app.md` links to those sections; `how-to/choose-how-to-start.md` adds the third way
- [x] 6.3 `survey/help_links.py` keys for the agent page links; test that every registry help anchor resolves to a heading; test that no help page has a Desktop config with `"url"`
- [x] 6.4 Changelog entry `survey/changelog/<date>-use-your-ai-assistant.html`

## 7. Translations and checks

- [x] 7.1 Append every new creator string to all offered catalogs by hand and compile (`TranslationCatalogHygieneTest`)
- [x] 7.2 Run `./run_tests.sh survey api mcp billing` (3149 tests, OK — after the change only; no separate baseline run) and `npm run build` in `help/` (links validator clean)
- [ ] 7.3 Verify in a browser on the dev server: card → page → tiles → status flips after a new MCP grant → prompt links; desktop and 390 px. Done with a grant written into the dev DB; still open: a REAL OAuth grant from Claude Code against a preview, together with 1.1
