## ADDED Requirements

### Requirement: Agent page
The system SHALL serve `GET /editor/surveys/start/agent/` (URL name `editor_survey_start_agent`)
to signed-in creators whose role in the active organization is `editor` or above, titled *Use your
AI assistant*, extending the editor base and rendering as a full page on every viewport. The page
SHALL show three steps — *Connect*, *Ask for a survey*, *Edit & publish* — and a way back to the
start page. The endpoint SHALL accept only GET. Viewers SHALL receive the same response as for any
editor-only page; signed-out visitors SHALL be sent to sign in.

#### Scenario: Editor opens the page
- **WHEN** an editor-or-higher creator opens `/editor/surveys/start/agent/`
- **THEN** the page shows the three steps, the client tiles and a link back to `/editor/surveys/start/`

#### Scenario: Viewer denied
- **WHEN** a viewer-role creator opens the page
- **THEN** the response is the standard editor-permission refusal

#### Scenario: Signed out
- **WHEN** an anonymous visitor opens the page
- **THEN** they are redirected to the login page

#### Scenario: POST refused
- **WHEN** the page URL receives a POST
- **THEN** the response is 405

### Requirement: One client registry
Every client the page offers SHALL be one entry of a single registry in code, carrying its slug,
display name, group (`chat` or `code`), connection method (`link`, `command`, `steps`,
`unsupported`), the vendor link or command where one exists, and its instruction steps. Tiles,
panels, the `?client=` parameter and event properties SHALL all be derived from that registry; no
template SHALL name a client outside it. The registry SHALL contain at least: Claude, ChatGPT,
Gemini, Le Chat, Perplexity, Microsoft Copilot Studio, an *unsupported* entry for assistants without
connectors, and *Something else* in the `chat` group; Cursor, VS Code, Claude Code, Codex, Windsurf
and Gemini CLI in the `code` group. Every URL the registry builds SHALL embed the server address
from `settings.MCP_RESOURCE_URL`, never a literal host.

#### Scenario: Tiles come from the registry
- **WHEN** the page renders
- **THEN** there is exactly one tile per registry entry, grouped under *Chat assistants* and *Coding tools*, chat assistants first

#### Scenario: Server address follows the setting
- **WHEN** `MCP_RESOURCE_URL` is `https://preview.example/mcp`
- **THEN** every install link, command and copy field on the page carries `https://preview.example/mcp` and none carries `mapsurvey.org`

#### Scenario: Unknown client parameter
- **WHEN** the page is opened with `?client=nonexistent`
- **THEN** it renders with the default tile selected and no error

### Requirement: Client selection
Choosing a tile SHALL show that client's panel without a page load and SHALL update the address to
`?client=<slug>`, so the panel can be linked to. Opened with `?client=<slug>`, the page SHALL show
that panel. Without the parameter it SHALL show the client chosen last in this browser, else Claude.
Each tile SHALL carry a short tag where it applies: *1 click* for `link` clients, *limited* for
Gemini, *not yet* for the unsupported entry.

#### Scenario: Direct link to a client
- **WHEN** the page is opened with `?client=chatgpt`
- **THEN** the ChatGPT tile is selected and its numbered steps are shown

#### Scenario: Default is Claude
- **WHEN** a creator opens the page for the first time without a parameter
- **THEN** the Claude tile is selected and its panel shown

#### Scenario: Remembered choice
- **WHEN** a creator chose Cursor earlier in this browser and opens the page without a parameter
- **THEN** the Cursor tile is selected

### Requirement: Per-client instructions
Each panel SHALL give the simplest path its client allows, and SHALL show a token, a URL to paste or
a configuration snippet only where that client needs one:
- `link` clients SHALL show one primary button that opens the vendor's install flow with Mapsurvey's
  name and server address filled in — for Claude
  `https://claude.ai/customize/connectors?modal=add-custom-connector&connectorName=Mapsurvey&connectorUrl=<encoded URL>`,
  for Cursor `cursor://anysphere.cursor-deeplink/mcp/install?name=mapsurvey&config=<base64 JSON>`,
  for VS Code `vscode:mcp/install?<encoded JSON>` — plus at most three short lines on what happens
  next (Claude: *Add*, *Connect*, *Allow*);
- `command` clients SHALL show one copyable command that signs in through the browser;
- `steps` clients SHALL show at most five numbered steps, the server address with a *Copy* button,
  and which authentication to choose (OAuth);
- the Claude panel SHALL say that one connector added there works in the web, desktop and phone
  apps, that Claude's free plan allows one custom connector, and that on Team and Enterprise plans
  an admin adds it;
- the ChatGPT panel SHALL say that it needs a computer and which ChatGPT plans can add a server.
The *Something else* panel SHALL give the server address, the transport, and both ways in: OAuth,
or a personal token from API & connections sent as `Authorization: Bearer`.

#### Scenario: Claude is one button
- **WHEN** the Claude panel is shown
- **THEN** it has one primary link whose `href` starts with `https://claude.ai/customize/connectors?modal=add-custom-connector` and carries `connectorName=Mapsurvey` and the encoded server address, and the panel shows no token and no field to copy

#### Scenario: Cursor install link is valid
- **WHEN** the Cursor panel is shown
- **THEN** its button's `config` parameter base64-decodes to JSON whose `url` is `MCP_RESOURCE_URL`

#### Scenario: ChatGPT steps
- **WHEN** the ChatGPT panel is shown
- **THEN** it shows numbered steps (no more than five), the server address with a *Copy* button, says to choose OAuth, and names the plans that can add a server

#### Scenario: Terminal command
- **WHEN** the Claude Code panel is shown
- **THEN** it shows `claude mcp add --transport http mapsurvey <MCP_RESOURCE_URL>` with a copy control and no token

### Requirement: Honest fallback when a client cannot connect
The *unsupported* entry SHALL state that the assistant cannot add connectors yet and that this is
the app's limit, and SHALL offer two ways forward: the Survey wizard (a link to the create page
with `?from=start` when a provider is configured) and Claude's free plan (selecting the Claude
tile). It SHALL offer *Tell us which*, a small form taking the assistant's name that records it as
an event and thanks the creator in place. The Gemini panel SHALL state its limits (country,
account type, plan) before its steps.

#### Scenario: Not yet
- **WHEN** the unsupported tile is chosen on a server with an LLM provider
- **THEN** the panel shows a link to `/editor/surveys/new/?from=start`, a control that selects the Claude tile, and the *Tell us which* form

#### Scenario: Tell us which
- **WHEN** a creator submits "DeepSeek" in *Tell us which*
- **THEN** `agent_client_requested` is emitted with the name truncated to 40 characters and the panel thanks them without a page load

#### Scenario: No provider
- **WHEN** the unsupported tile is chosen on a server without an LLM provider
- **THEN** the wizard option is not shown and the Claude option is

### Requirement: Connection detected without a click
While step 1 is open, the page SHALL poll `GET /editor/surveys/start/agent/status/?since=<timestamp>`
(URL name `editor_survey_start_agent_status`) at most every 3 seconds, and stop after 15 minutes or
when the tab is hidden, resuming when it is shown again. The endpoint SHALL answer JSON for the
signed-in creator only: `connected` is true when an OAuth access token of the creator with the
`mcp` audience was created after `since`, or a personal token of the creator with the `mcp`
audience was used after `since`; `client` is the connected application's display name (from
`api.oauth.grants.display_name`) or `null` for a personal token. It SHALL reveal no token value, no
scope and nothing about other users. On `connected`, the page SHALL mark step 1 done, show
*Connected* with the client name and a link to API & connections, and open step 2. A manual *I've
connected* link SHALL open step 2 at any time.

#### Scenario: OAuth grant detected
- **WHEN** the creator approves claude.ai on the Allow page while the agent page is open
- **THEN** the next poll answers `{"connected": true, "client": "<application name>"}` and the page shows step 1 as done and step 2 open

#### Scenario: Older grants do not count
- **WHEN** the creator connected an app yesterday and opens the page today
- **THEN** the status endpoint answers `connected: false` until a new grant is created or a token is used

#### Scenario: Other users' grants are invisible
- **WHEN** another user connects an app while this creator's page polls
- **THEN** this creator's status stays `connected: false`

#### Scenario: Manual override
- **WHEN** the creator clicks *I've connected* before any grant is detected
- **THEN** step 2 opens

### Requirement: Prompt step
Step 2 SHALL ask "What do you want to find out?" and build a prompt from one translatable template
that names the Mapsurvey tools, asks for a draft, tells the agent to ask about the place and
languages if unclear, and to return the editor link. The page SHALL offer *Open in Claude*
(`https://claude.ai/new?q=<encoded prompt>`), *Open in ChatGPT* (`https://chatgpt.com/?q=<encoded
prompt>`, the prompt prefixed with `@Mapsurvey`), and *Copy prompt* for every client; only the
buttons of the selected client's vendor SHALL be primary. An empty goal SHALL still produce a usable
prompt. The page SHALL say that the survey appears on the dashboard, with a link to it.

#### Scenario: Prompt carries the goal
- **WHEN** the creator types "Where people in Oak Park want new benches" and Claude is selected
- **THEN** *Open in Claude* links to `https://claude.ai/new?q=` followed by the encoded prompt containing that sentence, and *Copy prompt* copies the same text

#### Scenario: ChatGPT mention
- **WHEN** ChatGPT is selected
- **THEN** the ChatGPT prompt starts with `@Mapsurvey`

#### Scenario: Empty goal
- **WHEN** the goal field is empty
- **THEN** the prompt asks the agent to help draft a map survey and to ask the creator what it should find out

### Requirement: Pro notice before connecting
When the active organization does not have the `api` feature, step 1 SHALL show a notice that
connecting is possible now and that building surveys through an assistant needs Pro, with a link to
the plans page. With the feature, no notice SHALL be shown.

#### Scenario: Free workspace
- **WHEN** a creator whose active workspace is on Free opens the page
- **THEN** the notice and a link to the billing page are shown above the client panel

#### Scenario: Pro workspace
- **WHEN** the active workspace has the `api` feature
- **THEN** no Pro notice is shown

### Requirement: Agent onboarding events
The page SHALL emit `agent_client_chosen` (client slug) when a tile is chosen,
`agent_install_clicked` (client slug) when a primary install button or command copy is used,
`agent_connected` (client slug selected, `via` = `oauth` or `token`; never the application's
self-chosen name) once per page view
when detection succeeds, `agent_prompt_opened` (client slug, target `claude|chatgpt|copy`) and
`agent_client_requested` (free-text name, truncated). No event SHALL carry the goal text, a token,
a URL with a prompt, or survey content.

#### Scenario: Prompt text never leaves
- **WHEN** the creator opens the prompt in Claude
- **THEN** `agent_prompt_opened` carries `client` and `target` and no property holding the goal or prompt
