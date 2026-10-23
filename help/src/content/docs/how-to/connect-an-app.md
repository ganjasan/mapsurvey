---
# Nothing to connect TO yet: the authorization server shipped with change oauth-server
# (#313), the MCP server (#306) and the REST API (#380) are next. Remove `draft: true`,
# the `connected_apps` help link and the changelog entry together, in the PR of #306.
draft: true
title: Connect ChatGPT, Claude and other apps
description: Sign in once and let ChatGPT, claude.ai, Claude Code or any OAuth app work with your surveys — no token to copy, one click to disconnect.
sidebar:
  order: 15
---

Some apps cannot take a [personal access token](/how-to/personal-tokens/): ChatGPT's and
claude.ai's connector dialogs only know how to **sign you in**. Mapsurvey supports that flow. The
app sends you to a Mapsurvey page, you check what it asks for and press **Allow**, and the app
gets its own keys — limited to the permissions you allowed, revocable from your account at any time.

**The API is a Pro feature.** You can connect an app on any plan; calls on a survey answer
`pro_required` until that survey's workspace is on Pro.

## What the Allow page shows

- **The host first.** The address the app will send you back to (for example `claude.ai`) is the
  one thing an app cannot fake. The name under it is whatever the app calls itself — read the host.
- **What it may do.** Reading surveys, creating and editing them, reading responses are granted
  with Allow. **Publishing and deleting** are switches, off unless you turn them on: those calls
  cannot be undone.
- **Where.** Every workspace you belong to, with its plan.

Press **Cancel** to send the app away with nothing. Once you allowed an app, it will not ask
again unless it wants more than you granted.

## claude.ai (custom connector)

1. In claude.ai open **Settings → Connectors → Add custom connector**.
2. Enter the server URL Mapsurvey gives you for the MCP server (shown on **API & connections**
   once the MCP server is live) and save. Leave the OAuth fields empty — claude.ai discovers them.
3. Press **Connect**. A Mapsurvey tab opens: sign in if needed, read the Allow page, press
   **Allow**. You are sent back and the connector shows as connected.

## ChatGPT (Developer mode)

1. Turn on **Developer mode** under **Settings → Connectors → Advanced**.
2. **Create** a connector, enter the MCP server URL, choose **OAuth** as the authentication and
   save.
3. Press **Connect** and allow access on the Mapsurvey page that opens.

## Claude Code

```sh
claude mcp add --transport http mapsurvey <MCP server URL>
```

The first tool call opens your browser on the Allow page; Claude Code listens on a local port for
the answer (that is why the host on the Allow page reads `localhost (this computer)`).

## Any other OAuth app

Point it at `https://mapsurvey.org/.well-known/oauth-authorization-server`. The server supports
dynamic client registration, PKCE (S256), refresh tokens and `https` redirect addresses (plus
loopback `http://127.0.0.1` and `http://localhost` for desktop tools). There is nothing to
configure on the Mapsurvey side.

## See what is connected, disconnect

Open **API & connections** from your account menu. **Connected apps** lists every app you allowed
with its host, permissions, when you connected it and when it last called. **Disconnect** ends its
access at once; the app will have to ask again.

## Trouble?

- **"This app cannot connect"** with an error code — the app sent a request Mapsurvey refuses
  (an address it did not register, a missing PKCE challenge). Tell the app's maker the code.
- **The app connected but every call fails with `pro_required`** — the survey's workspace is on
  Free. See [Plans and billing](/reference/plans-and-billing/).
- **You expected to be asked and were not** — you allowed this app before with the same
  permissions. Disconnect it to be asked again.
