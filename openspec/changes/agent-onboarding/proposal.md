## Why

The MCP server is live (#306), yet the third card on the start page still says *Coming soon* and
leads nowhere. The only set-up instructions are on the help site and on API & connections, where
they start from a URL and a token — the vocabulary of developers, not of the planner or researcher
who already has Claude or ChatGPT open in another tab. Issue #312 asked for this card to become the
third real way to start; this change does it, with the rule that **every client gets the simplest
path its vendor allows, and nobody is left without one**.

## What Changes

- The *Connect your AI agent* card becomes a live link (one click, like the other two cards):
  renamed *Use your AI assistant*, no *Coming soon* tape, no `aria-disabled`, a *New* badge.
- New page `/editor/surveys/start/agent/` — **Use your AI assistant** — in three steps:
  1. **Connect.** A grid of client tiles in two groups — chat assistants (Claude, ChatGPT, Gemini,
     Le Chat, Perplexity, Microsoft Copilot Studio, "DeepSeek, Grok…", *Something else*) and coding
     tools (Cursor, VS Code, Claude Code, Codex, Windsurf, Gemini CLI). Each tile opens its own
     instruction, built from one registry:
     - **one button** where the vendor has an install link: Claude (`claude.ai` add-connector link,
       covers web, desktop and phone), Cursor (`cursor://` install link), VS Code (`vscode:` link);
     - **one command** for terminals: Claude Code, Codex, Gemini CLI;
     - **the fewest numbered steps** with a *Copy* button for the URL: ChatGPT, Le Chat, Perplexity,
       Copilot Studio, Gemini, Windsurf;
     - **an honest "not yet"** for assistants that cannot add connectors, offering the Survey wizard
       and Claude's free plan instead, and a *Tell us which* button.
     The page detects the connection by itself: it polls for a new MCP grant or the first MCP use of
     a token since the page opened, and shows *Connected ✓* without a click.
  2. **Ask for a survey.** "What do you want to find out?" → a prompt built from one template, with
     *Open in Claude* / *Open in ChatGPT* (prefilled `?q=` links) and *Copy prompt*.
  3. **Edit & publish** — a pointer to the dashboard where the agent's survey appears.
- Tokens, URLs and config snippets appear only in the panels of tools that need them; the chat
  assistants' path never shows a token.
- A Pro notice is shown **before** connecting when the active workspace is on Free, instead of
  `pro_required` in the middle of a chat.
- Events: `agent_client_chosen`, `agent_install_clicked`, `agent_connected`,
  `agent_prompt_opened`, `agent_client_requested` — client slug and outcome only.
- Help: `how-to/use-the-mcp-server.md` and `how-to/connect-an-app.md` rewritten per client to match
  the page. The Claude Desktop section was wrong: `claude_desktop_config.json` takes no `url` entry,
  so Desktop now connects as a connector. ChatGPT now uses its Plugins flow, not the old
  Developer-mode one. `how-to/choose-how-to-start.md` gains the third way. A changelog entry.
- **Not in this change** (separate issues): listings in the ChatGPT app directory and Claude's
  Connectors Directory (the real one-click path for those two); an MCPB bundle; an MCP Registry
  entry; #312's "Waiting for your agent's survey…" auto-redirect; a "via Claude" chip on the
  dashboard.

## Capabilities

### New Capabilities
- `agent-connect-page`: the *Use your AI assistant* page — the client registry and its tiles, the
  per-client instructions, the "not yet" fallback, connection detection, the prompt step, the Pro
  notice and the events.

### Modified Capabilities
- `survey-start-chooser`: the third card stops being inert and links to the agent page; its name,
  badge and text change.
- `help-site`: the MCP and connect-an-app pages follow the per-client instructions; the start guide
  names the third way.

## Impact

- Code: `survey/editor_views.py` (or a new `survey/agent_onboarding.py` for the registry and views),
  `survey/urls.py`, `survey/templates/editor/survey_start.html`, a new template and a small script
  under `survey/assets/js/`; a read-only status endpoint over `oauth2_provider` tokens through
  `api/oauth/grants.py` and `api.models.TokenProfile`.
- No model or migration. No change to the OAuth server, the redirect rules or the MCP server.
- `survey/product_events.py`: four event names; `survey/help_links.py`: keys for the new anchors.
- Translations: every new creator string in all offered catalogs.
- Depends on master after #306 (`MCP_RESOURCE_URL`). Closes #312 in its reduced scope.
