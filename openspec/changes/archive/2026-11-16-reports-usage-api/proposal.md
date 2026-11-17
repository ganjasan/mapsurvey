## Why

A report is written to be read, and its author cannot tell whether anyone read it: the public page
loads no analytics on purpose. A report also sits outside the two things every other object of a
workspace has — tags, and the API. An agent that can build a survey and read its answers cannot
write up what the survey found (issue #710, epic #712).

## What Changes

- **Readers.** Each report counts, per day, how often its page was opened, how often it was shown
  inside another site, and how often its PDF was downloaded. Counted on our server; no visitor is
  stored; members of the report's workspace are not counted. The numbers show in the editor's
  Settings and in the API.
- **Tags.** A report takes the workspace's tags (the Data module's `Tag`, one writer
  `data.tags.set_tags`), set in the editor's Settings, shown and filtered on the Reports list.
- **REST API v1** `/reports…`: list, create (empty or drafted from a survey by a template), read,
  change settings, add / change / reorder / delete blocks, read the pre-publication checks, publish,
  freeze, delete.
- **MCP**: the same as twelve tools. Publishing a report that shows quotes or individual marks, and
  deleting a report, need `confirm: true`.
- Help: the API reference and the MCP tool reference are regenerated; the report guide gains
  "Readers", "Tags" and "From your assistant".
- **What's new**: the epic's one hero entry.

## Capabilities

### New Capabilities
- `reports-usage-api`: reader counts, tags on reports, reports in REST API v1 and MCP.

### Modified Capabilities

## Impact

- `reports/usage.py`, `reports/blocks.py`, `reports/models.py` (`ReportUsage`), `reports/services.py`
  (`tags`, `delete_report`), `reports/files.py` (`entry_of`), `reports/views.py`,
  `reports/editor_views.py`, templates.
- `data/models.py` (`Tag.reports`), `data/tags.py`.
- `api/v1/reports.py`, `mcp/tools/reports.py`; generated `reference/api.md`, `reference/mcp-tools.md`.
- Migrations `reports/0008`, `data/0009`.
- `survey/changelog/2026-11-18-reports.html`.
