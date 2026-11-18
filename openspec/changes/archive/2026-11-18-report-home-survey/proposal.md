## Why

"New report" makes a report without a home survey (#737 made that one click), and such a report
can never show data: the block library offers only the "Write" tiles, the home survey cannot be
set afterwards, and Report settings show two switches ("Take the survey", "Link from the thanks
page") that do nothing without a survey. The canvas still promises "a chart or a map of a
question". Issue #739.

Most reports are about one survey, but a report may read several: blocks already name their own
dataset. So the home survey is a default that saves clicks, never a restriction, and it is chosen
at the moment it is first needed — in the block library — not on a step before the editor.

## What Changes

- The block library gets "Charts and maps from: [survey]". It starts on the report's home survey;
  a report without one starts on the workspace's only survey, or asks. Choosing another survey
  swaps the data tiles in place, so a block can come from any survey of the workspace.
- The first data block added to a report without a home survey makes that block's survey the home
  survey (when the author may edit that survey).
- Report settings get a "Survey" card: set, change or clear the home survey.
- The "Take the survey" and "Link from the thanks page" switches are shown only while the report
  has a home survey; their stored values are kept.
- A report started from a survey's page ("Make a report" on Responses / the dataset) is that
  survey's report even when it starts blank.
- A report somebody started is never auto-drafted by the survey's Public results tab.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `reports-editor`: choosing the survey a block reads, and the report's home survey.
- `reports-start`: a blank report started where the data is belongs to that survey.

## Impact

`reports/editor_views.py`, `reports/services.py`, `reports/render.py` (`scaffold_report`),
`reports/views.py` (`report_start`), the report URLs, the builder templates
(`_library.html`, new `_library_groups.html`, `_page_panel.html`), `js/report_builder.js`,
`css/report_builder.css`, the ten catalogs, the help page on reports. No migration.
