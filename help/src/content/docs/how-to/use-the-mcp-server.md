---
# The MCP server (mcp.mapsurvey.org) is not live yet: this page stays out of the build
# until it is. Remove `draft: true` and the TODO-verify note together.
draft: true
title: Use the MCP server
description: Connect Claude Desktop, Claude Code or Cursor to your Mapsurvey account with an MCP token and build surveys from a chat.
sidebar:
  order: 100
---

<!-- TODO verify: the MCP server, the MCP page in the editor navbar and the Generate / revoke labels come from docs/mcp.md; the server code is not in this repository, so confirm the feature is live before publishing this page -->

You end up with an MCP client that can list, create and edit your surveys when you ask it to — "add a polygon question to section 2 asking which area is busiest" — while responses and everything else stay in Mapsurvey.

## Before you start

- A Mapsurvey account, signed in at mapsurvey.org.
- One of: Claude Desktop, Claude Code or Cursor, with access to its MCP configuration.

## Steps

1. Open **MCP** in the editor navbar (the page is `/editor/account/mcp/`).
2. Press **Generate**, give the token a label such as `Claude Desktop @ laptop`, and copy it. It starts with `mscp_` and is shown once; keep it like a password.
   <!-- screenshot: the MCP page with a freshly generated token -->
3. Add the server to your client, replacing `mscp_…` with your token:

   **Claude Desktop** — open `claude_desktop_config.json` (on macOS under `~/Library/Application Support/Claude/`) and add:

   ```json
   {
     "mcpServers": {
       "mapsurvey": {
         "url": "https://mcp.mapsurvey.org/",
         "headers": { "Authorization": "Bearer mscp_…" }
       }
     }
   }
   ```

   Restart Claude Desktop; the Mapsurvey tools appear in the connector list.

   **Claude Code** — run:

   ```bash
   claude mcp add --transport http mapsurvey https://mcp.mapsurvey.org/ \
       --header "Authorization: Bearer mscp_…"
   ```

   **Cursor** — in the MCP settings, add a remote HTTP server at `https://mcp.mapsurvey.org/` with the same `Authorization` header.

4. Ask the model something. Examples that work well:
   - "List my surveys."
   - "Create a survey called Park improvements in English and German with a section about the playground."
   - "Add a point question to the first section asking where a new bench should go, with a sub-question rating how urgent it is."
   - "Set the survey to open https://example.org/thanks after the last page."
5. Open the survey in the editor to check the result. The model works on drafts; publishing and deleting need an explicit confirmation, so the model asks you before either.

## Result

The client holds a token scoped to your account: it can only see and change surveys you own or collaborate on, and Mapsurvey never sees the chat itself — only the tool calls. Each token allows 60 calls a minute and 5,000 a day.

**To revoke** a token, return to **MCP** in the editor and remove it; revocation takes effect immediately. Generate a second token for a second device or a second client rather than sharing one.

If the model reports "Survey is read-only — create a draft to edit", the survey is published or closed: start **Unpublished changes** in the editor first. If it reports a rate limit, wait a minute or use another token.

## Related

- [MCP tools](/reference/mcp-tools/) — every tool and error code
- [Question types](/reference/question-types/)
- [Edit a published survey](/how-to/edit-a-published-survey/)
