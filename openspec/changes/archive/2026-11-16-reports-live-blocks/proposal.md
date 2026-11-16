## Why

After `reports-story` a report reads as a story and a hand-made report can be imported, but its
charts and maps arrive as pictures. To replace them one by one with blocks that follow the data,
the story needs the blocks hand-made reports use most beyond a single question's chart: two
questions against each other, who took part, a map of the marks themselves, and numbers in the
text that stay true. The computations exist since `data-analysis-views` (#692); this change shows
them. Issue #704, second part (epic #712).

## What Changes

- **Cross-tab block**: two choice-type questions of the report's home survey against each other —
  a table of distinct respondents, masked and with withheld totals exactly as `data.analysis`
  returns it.
- **Engagement block**: opened → answered → finished and the series over time.
- Both blocks point at a `DatasetView` (`ReportBlock.view`); adding one makes the view in the Data
  module, so the same view is listed on the dataset page and "used by" names the report.
- **A map may show the marks themselves** (owner decision 2026-11-16: the survey owner's choice
  and responsibility): a per-block switch, off by default; on, the block carries the geometry of
  each mark and nothing else. **BREAKING** for the rule "a public map never carries an individual
  geometry": it now holds unless the author of a report switched it off for a block.
- **Live numbers in text**: tokens `{responses}`, `{opened}`, `{finished}`, `{marks:CODE}`,
  `{respondents:CODE}` in a Text block, a key number or the opening paragraph are filled from the
  home survey at render, masked under K, and fixed in a frozen report.
- The report file carries the new blocks and the map's switch.

## Capabilities

### New Capabilities
- `reports-live-blocks`: the cross-tab and engagement blocks, marks on a map, live numbers in text.

### Modified Capabilities
- `public-aggregates`: the map rule gains the author's per-block exception.
- `reports-import-export`: the file carries cross-tab and engagement blocks and the map's switch.

## Impact

- `reports/models.py` (+ `reports/0004`), `reports/render.py`, `reports/services.py`, new
  `reports/tokens.py`, `reports/story.py`, `reports/files.py`, `reports/editor_views.py`.
- `data/dataviews.py`: `result(view, lang, k)` takes the caller's K.
- Templates `public_results.html`, `editor/public_results.html`, `pr_add_block_modal.html`,
  `pr_block_list_item.html`; `js/public_results_render.js` (marks).
- Site results blocks and the Data API keep the grid: the exception is a report block's only.
