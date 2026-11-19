## Why

The report editor builds a map from several layers, each with its own view and settings, plus a
kept frame, a legend, a scale and a layer switch (#753), and it sets how a cross-tab is drawn
(#751). REST API v1 and the MCP server cannot do any of that: `get_report` returns those settings,
because a block is described by its report-file entry, but `add_report_block` and
`update_report_block` accept only `show_marks` and `description` for a map and nothing about a
cross-tab's look. An assistant can read a map it cannot rebuild. Issue #756, part of #712.

## What Changes

- `POST /api/v1/reports/{uuid}/blocks`, `PATCH …/blocks/{id}` and the MCP tools on top of them
  (`add_report_block`, `update_report_block`) accept, for a **map**: `view`, `opts`, `color`,
  `name`, `frame` (`null` clears it), `legend`, `scale`, `toggle`, `basemap`, `popup_fields` and
  `layers` (the whole list of the other map questions on the same map, at most 3). For a
  **crosstab**: `display = {view, values, sort}`.
- A layer is written with the names the block itself uses (`question`, `show_marks`,
  `popup_fields`) and is also accepted under the names `get_report` returns it with (`code`,
  `marks`, `fields`), so a layer read from `get_report` can be sent back unchanged.
- The API refuses with `422 validation`, naming the field, what the editor silently drops: an
  unknown view or option value, hot spots on a question that is not a point question, a layer
  that is not a map question of the workspace (or is the block's own question, or comes twice),
  more than 3 layers, a frame out of range, a basemap the workspace does not offer, a popup field
  that is not a non-text sub-question, and the Marks view with `show_marks: false`.
- The sub-questions a map popup may show are ONE helper shared by the editor panel and the API, so
  a free-text sub-question can reach a popup through neither.
- Writes go through `reports.services.update_block(map_display=…, crosstab_display=…)`, the
  editor's path; the editor's checks and the API's are one rule set
  (`services.layer_refusal`).
- The REST reference and the MCP tool reference are regenerated.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `reports-usage-api`: "Reports in REST API v1" and "Reports in MCP" gain the map and cross-tab
  settings, with strict refusals.

## Impact

- Code: `reports/blocks.py`, `reports/services.py` (`layer_refusal`, `_checked_layers`),
  `reports/sources.py` (`popup_subquestions`, moved from `editor_views._geo_subquestions`),
  `api/v1/reports.py` (schemas), `mcp/tools/reports.py` (descriptions).
- Generated: `help/src/content/docs/reference/api.md`, `help/src/content/docs/reference/mcp-tools.md`.
- No migration, no change to the report file format or to `get_report`'s output.
- Not in scope: context layers from Data, areas shaded by answers, a filter by sub-question (none
  exists in the editor yet), image blocks through the API.
