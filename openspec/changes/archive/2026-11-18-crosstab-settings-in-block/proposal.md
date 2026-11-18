## Why

The Cross-tab and Compare tiles of the block library open a form inside the library, and a block,
once added, cannot be changed — its panel tells the author to add another one (#751). The Reports
journey board (screen S3, "Tune a chart block") drew the block's own settings instead: the question,
what it is split by, suggested views, % or count, sort.

## What Changes

- The Cross-tab tile adds the block in one click with the first two questions a cross-tab may
  name; the Compare tile with the first question that has a comparable twin in another survey.
  The library forms go.
- The cross-tab block's panel (Data): **Question** (rows), **Split by** (columns), **Suggested
  views** `bars | stacked | ranking | table`, **Values** `percent | count`, **Sort by value**.
  Display choices live in `ReportBlock.config`; changing the questions points the block at another
  `DatasetView` (an identical one is reused, else made through `data.services.create_view`), and the
  view it leaves is deleted when the report made it (auto name) and nothing else shows it.
- The page draws the chosen view from the Data module's payload: shares are cell ÷ the group's
  total; a group whose total is withheld is left out of the bars and named in a note; nothing is
  recounted. A block without display settings (made before) stays a table. The PDF, the PNG and the
  CSV keep the table.
- The Compare block's panel: **Question** and **Compare with**, checked by `services.comparable`.

## Capabilities

### Modified Capabilities
- `reports-live-blocks`: the cross-tab is added in one click, set up and redrawn in its panel.
- `reports-reuse`: the Compare block is added in one click and set up in its panel.

## Impact

`reports/services.py`, `reports/story.py`, `reports/render.py`, `reports/editor_views.py`,
`reports/templates/reports/_block.html`, `reports/templates/reports/editor/_library_groups.html`,
`reports/templates/reports/editor/_block_panel.html`, `css/report_public.css`,
`css/report_builder.css`; tests in `survey/tests/test_reports_live_blocks.py` and
`test_reports_reuse.py`; catalogs.
