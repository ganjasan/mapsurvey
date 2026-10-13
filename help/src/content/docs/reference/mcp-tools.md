---
# The MCP server (mcp.mapsurvey.org) is not live yet: this page stays out of the build
# until it is. Remove `draft: true` and the TODO-verify note together.
draft: true
title: MCP tools
description: The Mapsurvey MCP server for Claude Desktop, Claude Code and Cursor — connection details, every tool it exposes, and the error codes it returns.
sidebar:
  order: 60
---

<!-- TODO verify: the MCP server and the token page /editor/account/mcp/ are described in docs/mcp.md and docs/mcp-tools.md but their code is not in this repository; confirm the service is live at https://mcp.mapsurvey.org/ and that the page labels below match before publishing -->

The Mapsurvey MCP (Model Context Protocol) server lets an MCP-capable client — Claude Desktop, Claude Code, Cursor and others — read, build and edit your surveys from a chat. It exposes the same operations the editor uses, scoped to the account that generated the token. For setup, see [Use the MCP server](/how-to/use-the-mcp-server/).

## Connection

| | |
|---|---|
| Server URL | `https://mcp.mapsurvey.org/` (HTTP transport) |
| Authentication | `Authorization: Bearer mscp_…` header; tokens are made and revoked at **MCP** in the editor navbar (`/editor/account/mcp/`) |
| Scope | Only surveys the token's user owns or collaborates on |
| Rate limit | 60 calls a minute and 5,000 a day per token |
| Audit | Every call is logged with the tool name, user, time and outcome; argument values over 200 characters are stored as a length only |

Mapsurvey never sees your conversation with the model — only the tool calls the model decides to make.

## Tools

### Reads

| Tool | What it does |
|---|---|
| `list_surveys(status?)` | Your accessible surveys, optionally filtered by status |
| `get_survey(uuid)` | The full structure of one survey |

### Survey

| Tool | What it does |
|---|---|
| `create_survey(name, languages?, organization_uuid?)` | A new empty draft; returns its uuid, name and status |
| `set_survey_meta(uuid, name?, redirect_url?, visibility?, thanks_html?, password?)` | Changes top-level fields; pass only what you want to change |
| `set_languages(uuid, languages)` | Replaces the available languages (ISO 639-1 codes) |
| `delete_survey(uuid, confirm)` | Deletes the survey and its responses. Needs `confirm=true` |

### Sections

| Tool | What it does |
|---|---|
| `create_section(survey_uuid, name, title?, subheading?, use_geolocation?)` | Adds a section at the end |
| `update_section(section_id, name?, title?, subheading?, use_geolocation?)` | Changes a section |
| `delete_section(section_id)` | Removes a section |
| `reorder_sections(survey_uuid, section_ids)` | Pass every existing section id in the new order |

### Questions

| Tool | What it does |
|---|---|
| `add_question(section_id, input_type, name, subtext?, required?, choices?, parent_question_id?)` | Adds a question at the end of the section; with `parent_question_id` it becomes a sub-question, which cannot be a map type |
| `update_question(question_id, name?, subtext?, input_type?, required?, choices?)` | Changes a question |
| `delete_question(question_id)` | Removes a question with its sub-questions and answers |
| `reorder_questions(section_id, question_ids)` | Reorders top-level questions; sub-questions keep their order |
| `set_choices(question_id, choices)` | Replaces the options; each is `{code, name}` with `name` a string or a `{lang: text}` map |

### Publishing and bulk

| Tool | What it does |
|---|---|
| `publish_survey(uuid, confirm)` | Draft → published. Needs `confirm=true` |
| `import_survey_json(blob)` | Imports a complete survey in one call |

Tools that change a survey work on drafts only; a published or closed survey answers with a `lifecycle` error. Creating the unpublished-changes copy is done in the editor.

### Resources

| Resource | Contents |
|---|---|
| `mapsurvey://docs/question-types` | Which input type fits which question |
| `mapsurvey://docs/choices-format` | The multilingual options format |
| `mapsurvey://docs/serialization-schema` | The bulk-import format |
| `mapsurvey://survey/<uuid>` | The current state of a survey |

## Error codes

| Code | Meaning |
|---|---|
| `forbidden` | The token is missing, revoked or malformed |
| `not_found` | The survey, section or question does not exist or is not yours |
| `validation` | An argument is the wrong shape or breaks a rule — for example a map-type sub-question |
| `lifecycle` | The survey is read-only because it is published or closed |
| `confirm_required` | A destructive tool was called without `confirm=true` |
| `incompatible` | Publishing was refused because the draft has changes incompatible with the live version |
| `rate_limit` | The token's limit was reached; wait for the window to reset or use a second token |

## Related

- [Use the MCP server](/how-to/use-the-mcp-server/)
- [Question types](/reference/question-types/)
