---
title: Use the MCP server
description: Connect Claude, ChatGPT, Gemini, Le Chat, Perplexity, Cursor, VS Code, Claude Code, Codex and other assistants to your Mapsurvey account and build, edit and publish surveys from a conversation.
sidebar:
  order: 16
---

You end up with an AI assistant that can build and edit your surveys and report on what came back
when you ask it to — "add a point question to the first section asking where a new bench should go,
with a sub-question rating how urgent it is", "summarise the answers and map where people want
benches" — while the data stays in Mapsurvey.

The quickest way in is the product itself: **New Survey → Use your AI assistant** shows a tile for
every assistant below, with one button or one command where the assistant allows it, and notices
by itself when you are connected. This page is the same set of instructions, for reference.

The server speaks the **Model Context Protocol (MCP)**, which is what Claude, ChatGPT, Cursor and
most agent tools use to reach outside services. Its address is one URL:

```
https://mapsurvey.org/mcp
```

**The MCP server is a Pro feature.** You can connect on any plan; tools on a survey answer
`pro_required` until the workspace that owns it is on Pro. See
[Plans and billing](/reference/plans-and-billing/).

## Two ways to connect

- **Sign in through the assistant** — every assistant below opens a Mapsurvey page where you check
  what it asks for and press **Allow**. No token to copy; disconnect from your account at any time.
  See [Connect ChatGPT, Claude and other apps](/how-to/connect-an-app/) for what the Allow page
  shows.
- **A personal token** — for scripts and for a client that only takes a header. Create one under
  **API & connections** for the **MCP server** (see
  [Create a personal access token](/how-to/personal-tokens/)), send it as
  `Authorization: Bearer msk_…`, and keep **publish** and **delete** off unless the agent must do
  those.

## Chat assistants

### Claude

One connector serves Claude on the web, the desktop app and your phone.

1. Open
   [this link](https://claude.ai/customize/connectors?modal=add-custom-connector&connectorName=Mapsurvey&connectorUrl=https%3A%2F%2Fmapsurvey.org%2Fmcp)
   (or **Customize → Connectors → Add custom connector** and enter `https://mapsurvey.org/mcp`). The
   name and address are filled in: press **Add**.
2. Press **Connect** next to Mapsurvey.
3. Sign in to Mapsurvey if needed, read the Allow page, press **Allow**.

Claude's free plan allows one custom connector. On a Team or Enterprise plan an owner adds it once
under **Organization settings → Connectors** and members press **Connect**. Claude Desktop does not
read remote servers from its configuration file; use the connector.

### ChatGPT

On a computer, with a paid plan. Some plans let only workspace admins add a server; if you do not
see the option, your plan does not include it.

1. Open ChatGPT, go to **Plugins**, press **+** and choose **Add custom MCP server**.
2. Name it Mapsurvey, enter `https://mapsurvey.org/mcp` and choose **OAuth**.
3. ChatGPT warns about custom servers; that is expected. Press **Create**, then **Connect**.
4. On the Mapsurvey page that opens, press **Allow**.

In a chat, mention **@Mapsurvey** so ChatGPT uses it.

### Gemini

Only in the US, with a personal Google account, in English, and inside Spark tasks.

1. On gemini.google.com open **Settings → Connected apps → Add a custom app**.
2. Enter `https://mapsurvey.org/mcp` and press **Next**.
3. On the Mapsurvey page that opens, press **Allow**.

### Le Chat

1. In Le Chat open **Connectors → + Add Connector → Custom MCP Connector**.
2. Name it Mapsurvey and enter `https://mapsurvey.org/mcp`.
3. Press **Connect**, then **Allow** on the Mapsurvey page.

### Perplexity

Needs a Pro, Max or Enterprise plan.

1. Open **Customize → Connectors → + Custom connector → Remote**.
2. Name it Mapsurvey, enter `https://mapsurvey.org/mcp`, choose **Streamable HTTP** and **OAuth**.
3. On the Mapsurvey page that opens, press **Allow**.

### Copilot Studio

For agents built in Microsoft Copilot Studio; the Copilot app itself cannot add outside tools yet.

1. In your agent open **Tools → Add a tool → New tool → Model Context Protocol**.
2. Name it Mapsurvey and enter `https://mapsurvey.org/mcp`.
3. Choose **OAuth 2.0 → Dynamic discovery**, create the connection and press **Allow** on the
   Mapsurvey page.

### Something else

Any MCP client that can add a remote server: address `https://mapsurvey.org/mcp`, transport
**Streamable HTTP**, sign-in with **OAuth** (the client opens the Allow page). A client that only
takes a header gets a personal token as `Authorization: Bearer msk_…`.

DeepSeek, Grok and most other chats cannot add connectors yet. Use the Survey wizard
([Choose how to start a survey](/how-to/choose-how-to-start/)), which needs no other app, or
Claude's free plan.

## Coding tools

### Cursor

The **Add Mapsurvey to Cursor** button in the product opens
`cursor://anysphere.cursor-deeplink/mcp/install?name=mapsurvey&config=eyJ1cmwiOiAiaHR0cHM6Ly9tYXBzdXJ2ZXkub3JnL21jcCJ9`:
press **Install**, then **Allow** when Cursor sends you to sign in. By hand, add to
`~/.cursor/mcp.json`:

```json
{ "mcpServers": { "mapsurvey": { "url": "https://mapsurvey.org/mcp" } } }
```

### VS Code

The **Add Mapsurvey to VS Code** button in the product opens VS Code with the server filled in:
press **Install**, then **Allow** when it sends you to sign in. From a terminal:

```sh
code --add-mcp '{"name":"mapsurvey","type":"http","url":"https://mapsurvey.org/mcp"}'
```

### Claude Code

```sh
claude mcp add --transport http mapsurvey https://mapsurvey.org/mcp
```

The first tool call opens the Allow page in your browser. Connectors added on claude.ai appear here
too. To skip the sign-in on a machine without a browser, pass a token instead:

```sh
claude mcp add --transport http mapsurvey https://mapsurvey.org/mcp \
    --header "Authorization: Bearer msk_…"
```

### Codex

```sh
codex mcp add mapsurvey --url https://mapsurvey.org/mcp
codex mcp login mapsurvey
```

The second command opens the Allow page.

### Windsurf

In the Cascade panel open **⋯ → Open MCP config**, add Mapsurvey under `mcpServers`, save, and sign
in when Windsurf asks:

```json
"mapsurvey": { "serverUrl": "https://mapsurvey.org/mcp" }
```

### Gemini CLI

```sh
gemini mcp add --transport http mapsurvey https://mapsurvey.org/mcp
```

Then run `/mcp auth mapsurvey` inside Gemini CLI. Antigravity CLI reads the same address from
`"serverUrl"` in `mcp_config.json`.

## First conversation

Ask the agent to **check who it is first** — it should call `get_me`, which tells it your
workspaces, which of them include the API, and which tools it may use. Then try:

- "List my surveys."
- "Create a survey called Park improvements in English and German with a section about the
  playground."
- "Add a point question to the first section asking where a new bench should go, with a
  sub-question rating how urgent it is."
- "Set the survey to open https://example.org/thanks after the last page."
- "Publish it." — the agent asks you to confirm before it does.

To put context on the map:

- "Add the city's bus stops from this GeoJSON as a layer, blue, labelled by stop name." — the agent
  passes the GeoJSON to `create_layer` (WGS 84 longitude/latitude, at most 5 000 features) and
  styles it with `update_layer`.
- "Ask people to rate each of these stops." — an "Objects on the map" question bound to that layer.
- "Turn the benches people marked into a shared map others can vote on, and hide the mark #3 that
  is spam." — `layer_from_answers` on the question, then `moderate_layer_object`.

Layers and their objects are changed only with the survey owner's role; deleting asks you first.

To send it out:

- "Give me the link and a QR code for a poster." — the link, and the QR as an image in the chat
  (`get_share_links`, `get_qr_code`).
- "Make separate links for the newsletter and the flyers." — tracked links, so the responses from
  each are counted apart (`create_tracked_link`, `list_tracked_links`).
- "Give me the code to embed it on our website, and allow only city.gov." — the embed snippet and
  the allowed sites (`set_embed_hosts`).

Once responses come in:

- "Summarise the responses to Park improvements." — counts and distributions per question
  (`get_response_summary`).
- "What did people write about the playground?" — the comments themselves (`list_text_answers`).
- "Show me where people drew the areas that need lighting." — the map answers as GeoJSON
  (`get_answer_geojson`).
- "Give me the answers as an Excel file." — a download link that works for 15 minutes
  (`get_export_link`).
- "Reject response #12, it is spam." — only if you switched on **Approve, hold or reject
  responses** when connecting (`moderate_response`).

The numbers match the export: empty, deleted and rejected responses are left out unless you ask
for them.

Open the survey in the editor to check the result. [MCP tools](/reference/mcp-tools/) lists every
tool with its arguments.

## What the agent can and cannot do

- It sees and changes only surveys you own or collaborate on, within the permissions you allowed. A
  viewer stays a viewer whatever the agent asks for.
- On a **published** survey, wording changes apply in place; structural changes (adding, deleting or
  reordering questions, changing a type) go through **unpublished changes**, exactly as in the
  editor. The agent gets a `draft_required` answer and knows to start them.
- **Publishing and deleting always ask for confirmation.** The agent cannot delete a survey that
  respondents have answered; that is done in the editor, where the answers are shown first.
- It reads responses only with **Read and export responses**, and changes a response's status only
  with **Approve, hold or reject responses** — a switch that is off unless you turn it on. It never
  edits or deletes answers.
- Respondents' text reaches the agent as data, under a note that it is not instructions — the same
  mitigation as for survey content (see below).
- Mapsurvey never sees your conversation — only the tool calls the agent makes, logged by name and
  outcome.

## A word on safety

An agent that reads survey content can be influenced by it. Every answer the server gives wraps
what people wrote — titles, option labels, help texts — in a `data` field with a fixed note that it
is information, not instructions, and the agent is told to treat it that way. That is a mitigation,
not a guarantee: keep **publish** and **delete** behind confirmation (the default), review what an
agent built before you publish, and grant a token only the permissions its job needs.

## Troubleshooting

- **The client says "could not connect" or asks you to authenticate again** — the token was revoked
  or expired, or the app's grant was disconnected. Create a token or connect again.
- **Every tool answers `pro_required`** — the survey's workspace is on Free. Upgrade it, or ask the
  agent to work in a Pro workspace (`get_me` lists them).
- **`draft_required`** — the survey is live; let the agent start unpublished changes and edit those.
- **`rate_limited`** — the agent is looping. Wait the seconds it names; the limits are 60 writes a
  minute per token and 300 tool calls per 10 minutes per session.
- **The agent did something you did not ask for** — disconnect it (API & connections → Disconnect,
  or revoke the token) and check the survey's audit trail in the editor.

## Related

- [MCP tools](/reference/mcp-tools/) — every tool and error code
- [Connect ChatGPT, Claude and other apps](/how-to/connect-an-app/)
- [Create a personal access token](/how-to/personal-tokens/)
- [Edit a published survey](/how-to/edit-a-published-survey/)
