---
title: Use the MCP server
description: Connect Claude, ChatGPT, Claude Code, Claude Desktop or Cursor to your Mapsurvey account and build, edit and publish surveys from a conversation.
sidebar:
  order: 16
---

You end up with an AI agent that can list, build and edit your surveys when you ask it to — "add a
point question to the first section asking where a new bench should go, with a sub-question rating
how urgent it is" — while responses and everything else stay in Mapsurvey.

The server speaks the **Model Context Protocol (MCP)**, which is what Claude, ChatGPT, Cursor and
most agent tools use to reach outside services. Its address is one URL:

```
https://mapsurvey.org/mcp
```

**The MCP server is a Pro feature.** You can connect on any plan; tools on a survey answer
`pro_required` until the workspace that owns it is on Pro. See
[Plans and billing](/reference/plans-and-billing/).

## Two ways to connect

- **Sign in through the app** — claude.ai, ChatGPT and Claude Code open a Mapsurvey page where you
  check what the app asks for and press **Allow**. No token to copy; disconnect from your account
  at any time. See [Connect ChatGPT, Claude and other apps](/how-to/connect-an-app/) for what the
  Allow page shows.
- **A personal token** — Claude Desktop, Cursor and scripts take a token in a header. Create one
  under **API & connections** for the **MCP server** (see
  [Create a personal access token](/how-to/personal-tokens/)) and keep **publish** and **delete** off
  unless the agent must do those.

## Steps

### claude.ai

1. Open **Settings → Connectors → Add custom connector**.
2. Enter `https://mapsurvey.org/mcp` as the server URL and save; leave the OAuth fields empty.
3. Press **Connect**, sign in to Mapsurvey if needed, read the Allow page, press **Allow**.

### ChatGPT

1. Turn on **Developer mode** under **Settings → Connectors → Advanced**.
2. **Create** a connector with the URL `https://mapsurvey.org/mcp` and **OAuth** as the
   authentication.
3. Press **Connect** and allow access on the Mapsurvey page that opens.

### Claude Code

```sh
claude mcp add --transport http mapsurvey https://mapsurvey.org/mcp
```

The first tool call opens the Allow page in your browser. To skip the sign-in on a machine without
a browser, pass a token instead:

```sh
claude mcp add --transport http mapsurvey https://mapsurvey.org/mcp \
    --header "Authorization: Bearer msk_…"
```

### Claude Desktop

Open `claude_desktop_config.json` (on macOS under `~/Library/Application Support/Claude/`) and add:

```json
{
  "mcpServers": {
    "mapsurvey": {
      "url": "https://mapsurvey.org/mcp",
      "headers": { "Authorization": "Bearer msk_…" }
    }
  }
}
```

Restart Claude Desktop; the Mapsurvey tools appear in the connector list.

### Cursor

In the MCP settings, add a remote HTTP server at `https://mapsurvey.org/mcp` with the same
`Authorization` header.

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
- It does not read responses in this version.
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
