## Why

Before merging the Data epic, the owner asked what the switch to grids (#666) does to the 22 live
`/r/` pages with maps. Measured on production data (2026-11-16, read-only), a fixed grid of 40 cells
across the answers' extent left 11 of 19 customers' pages with an EMPTY map: on a small survey almost
every cell holds fewer than K people. And an empty map was centred on Berlin, with no word of why.

## What Changes

- **Adaptive grid** in `data.aggregate.grid`: without a fixed `cells_across`, the finest of 40 / 20 /
  10 / 5 cells across that shows at least 60 % of the respondents is used, else the one showing the
  most. Cells under K stay omitted whatever the size: a coarser grid shows more people, never anyone
  alone. Public results, Site results blocks and grid views of Data use it.
- **Say why**: the payload carries `respondents_hidden` and a translated `note`. A map with no cell
  shows the note instead of an empty map ("Not enough answers yet to show this map without revealing
  anyone …"); a map with hidden respondents adds it to its caption. Creators see the same in the
  page's preview.
- Measured effect with the adaptive grid: the Alief survey's maps go from 0 % of respondents shown to
  27–77 %, Crime Watch from 0 % to 36 %, a 5-person polygon map from 0 % to 60 %; maps that stay empty
  have 1–4 respondents far apart — those now show the note.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `public-aggregates`: the map requirement gains the adaptive cell size and the visitor-facing note.

## Impact

- `data/aggregate.py`, `survey/public_results.py`, `survey/assets/js/public_results_render.js`;
  tests in `survey/tests/test_public_aggregates.py`; strings in 10 catalogs.
