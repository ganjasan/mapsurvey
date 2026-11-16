## Why

Today a report's privacy is checked by eye and "Publish" is one click with no questions. Since
`reports-story` and `reports-live-blocks` a report can carry hand-picked quotes and a map of
individual marks — the survey owner's decision, which the product should make sure was a decision.
Issue #706 (epic #712).

## What Changes

- **"Before you publish"** (`reports/checks.py`): a list shown in a publish dialog — first what
  names or places people (every visible quote, written out; every map that shows marks; a
  threshold of 1), then what looks unfinished (a block that renders nothing, a map without a
  description for screen readers, a missing title, how many blocks are hidden), each with a
  one-click way to fix it.
- **Publishing a report with quotes or marks needs a confirmation** ("I have read the quotes and
  maps listed above"); nothing else holds a publication back. **BREAKING** for scripts posting
  `publish=1` to such a report without `ack=1`.
- **The publish dialog** also asks who can open the report and whether its numbers are live or
  frozen, and shows the address.
- **A map block gets a description** — one sentence shown under the map and read to people who
  use a screen reader.
- **Preview as on a phone or a computer** in the editor's preview pane.
- Events `report_published` (visibility, mode) and `report_previewed` (device).

## Capabilities

### New Capabilities
- `reports-review`: the checks, the confirmation, the publish dialog, map descriptions, the
  preview widths.

### Modified Capabilities

None.

## Impact

- New `reports/checks.py`, `editor/partials/pr_checks.html`; `reports/services.py`
  (`set_published(ack, visibility, mode)`), `reports/editor_views.py` (`_checks`),
  `reports/render.py` (map description), `survey/urls.py`, `survey/product_events.py`,
  `editor/public_results.html`, `public_results.html`.
- Not here: comment threads on a report without a home survey (threads hang on a survey; blocks
  of a survey's report already have them), the PDF preview and page-break check (#707).
