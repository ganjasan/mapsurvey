## Context

Reports (epic #712) has one write path, `reports.services`, with a dual-route editor on top. The
REST API and the MCP server already expose surveys and the Data module through shared helpers in
`api/v1/` that MCP tools import. Respondent-facing and public pages load no third-party analytics.

## Goals / Non-Goals

**Goals:** an author sees whether a report is read; a report is tagged like a survey or a dataset;
an agent can draft, write, check and publish a report with the rules of the editor.

**Non-Goals:** who read it, from where, for how long (no visitor data); uploading pictures through
the API (image blocks stay an editor action); per-block usage; an API for the PDF job.

## Decisions

- **One row per report, day and kind** (`ReportUsage`), incremented with an `UPDATE … count + 1`
  and created on the first hit of the day. No row per view: nothing about a reader exists to leak,
  and the table grows by at most three rows a day per report. Alternative — PostHog server events —
  rejected: public pages are deliberately outside PostHog, and the number must live where the
  customer's data lives.
- **Members are not counted**: a signed-in member of the report's workspace opening the page is the
  author checking their work. Anonymous repeat visits are counted — without storing a visitor there
  is nothing to de-duplicate by, and "times opened" is what the label says.
- **`embed` vs `view`** by the `?embed=1` parameter the snippet already carries; a single block's
  page counts for its report.
- **Counting never breaks a page**: any failure is logged and swallowed.
- **Tags reuse `data.Tag`** with a third relation, as the model's docstring prescribes.
- **Blocks from plain values** (`reports/blocks.py`): a spec dict → the same service calls the
  editor's form handlers make. What the API returns for a block is the report file's entry of it
  (`files.entry_of`), so there is one description of a block outside the database.
- **Scopes are the surveys'** (`surveys:read|write|publish|delete`): a report is part of the work a
  survey's editor already does, and a new scope would invalidate every existing token for it.
- **Two gates on the API**: the workspace's API plan (`require_pro_api`, as for every resource) and,
  on writes, the Reports feature (`reports.gate.use`, as in the editor).
- **Confirmation**: REST publishes a report with quotes or marks only with `confirm: true` (409
  `conflict` otherwise — the editor's `ack_required`); MCP answers `confirmation_required` before
  calling the service, so the agent reads the checks to the person. `show_marks` on a map is the
  survey owner's decision (owner, 2026-11-16) and is not separately confirmed; the publish
  confirmation covers it.

## Risks / Trade-offs

- Bots inflate "times opened" → the label says opened, not people; no claim of unique readers.
- A write-heavy counter on a public page → one indexed UPDATE per view; reports are low-traffic
  pages, and the snapshot / 60-s cache keeps the rest of the request cheap.
