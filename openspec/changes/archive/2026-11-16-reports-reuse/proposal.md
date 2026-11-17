## Why

A second round of an engagement asks mostly the same questions, and its report tells mostly the
same story. Today round two starts from a blank report, or from a copy whose charts still show
round one. And nothing shows the two rounds next to each other (issue #711, epic #712).

## What Changes

- **Copy an earlier report onto another survey.** The copy keeps the opening, the text, the order
  and every setting of each block, and points every chart, map, cross-tab and engagement block at
  the chosen survey, matching questions by their code. A block whose question the survey does not
  have is not dropped silently: it stays in the copy as a hidden note naming what it showed, and
  the author is told which blocks those are.
- **Compare block.** One question in two rounds side by side: the share of each answer in the
  report's survey and in another survey of the workspace that has a question with the same code.
- Event `report_reused` (ids and counts only).
- The report file, the API and MCP know the new block type.

## Capabilities

### New Capabilities
- `reports-reuse`: copying a report onto another survey with rebinding by question code, and the
  Compare block.

### Modified Capabilities

## Impact

- `reports/files.py` (`import_report(onto=)`, `entry_of`), `reports/drafting.py` (`copy_report`),
  `reports/views.py` + `start.html` (the copy card), `reports/models.py` (`compare` type; migration),
  `reports/services.py` (`add_compare_block`), `reports/render.py` (`_compare_payload`),
  `reports/pdf.py`, `reports/tables.py`, `reports/blocks.py`, `api/v1/reports.py`,
  `survey/templates/public_results.html`, the Add block dialog, `survey/product_events.py`.
