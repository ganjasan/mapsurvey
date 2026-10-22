---
title: Create a personal access token
description: Give a script, a GIS tool or an AI agent access to your surveys with a token you can revoke any time.
sidebar:
  order: 14
---

A personal access token lets something that is not a browser act as you: a Python script, a QGIS
plug-in, Claude Code, Cursor. It carries the permissions you pick, reaches the workspaces you allow,
and can be revoked with one click.

**The API is a Pro feature.** You can create tokens on any plan, but calls on a survey answer
`pro_required` until the workspace that owns that survey is on Pro. See
[Plans and billing](/reference/plans-and-billing/).

## Create a token

1. Open the account menu (your initials, top right) → **API & connections**.
2. Under **New token**, give it a name you will recognise later ("QGIS plug-in", "Claude Code").
3. Pick **permissions**. Read, write and responses are on by default; **publish** and **delete**
   are off — switch them on only for a tool that must do those, because they cannot be undone.
4. Pick what it is for: the **REST API**, the **MCP server**, or both.
5. Optionally limit it to one **workspace**. "All my workspaces" is the default.
6. Choose when it **expires**: 90 days, 1 year, or never.
7. Click **Create token**.

The full value is shown **once**. Copy it into your tool now; after you leave the page only the
last four characters remain visible. Lost it? Revoke that token and create another — it costs
nothing.

## Use it

Send it as a bearer header:

```bash
curl -H "Authorization: Bearer msk_…" https://mapsurvey.org/api/v1/me
```

`/api/v1/me` answers with your user, every workspace the token reaches with its plan and whether
the API is available there, and the token's own permissions. Call it first from any new
integration: it tells you about `pro_required` before a real call fails.

## Permissions

| Permission | Allows |
|---|---|
| `surveys:read` | Read surveys, sections, questions |
| `surveys:write` | Create and edit them |
| `surveys:publish` | Publish, close and reopen |
| `surveys:delete` | Delete a survey |
| `responses:read` | Read and export responses |

A token never does more than you could do in the browser. A viewer on a survey stays a viewer
whatever the token's permissions say; a survey you cannot see does not exist to the token.

## Revoke a token

On **API & connections**, click **Revoke** next to the token. Anything using it stops working at
once. Tokens also stop at their expiry date, and when a workspace leaves Pro its surveys stop
answering API calls until it returns — the token itself stays valid.

## Limits

Each token may make 600 reads and 60 writes a minute and 5 000 calls a day, with separate daily
caps on creating (50) and deleting (20) surveys. Over the limit you get `429 rate_limited` with a
`Retry-After` header. If a tool needs more, [tell us](/faq/#contact).

## Security notes

- Treat a token like a password. Put it in your tool's settings or an environment variable, not
  in a file you commit.
- Prefer a workspace-bound token for a tool that only needs one workspace.
- Prefer an expiry for anything that runs unattended.
- Tokens are stored hashed on our side: nobody at Mapsurvey can read yours back.
