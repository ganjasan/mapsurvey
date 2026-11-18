## Why

The reports made by hand for customers (the materials kits of autumn 2026) draw a map question three
ways the report builder cannot: soft shading where people marked, numbered hot spots with a ranked
list beside the map, and a frame the author chose — the whole town on one map, one neighbourhood on
the next. The builder's map block shows squares that count respondents (or the raw marks), always
fitted to all the answers (#753).

## What Changes

- A map block has a **view**, picked in its panel as a cross-tab's is: `heat` (shading), `hotspots`
  (point questions: numbered places, largest first, listed under the map), `squares`, `marks`.
  A new block starts as heat; a block made before keeps its squares (or its marks).
- Privacy is unchanged by default: heat is drawn from the cells that count respondents, a hot spot
  needs at least K distinct respondents (and two marks). The per-block switch — now "Use every
  mark" — builds both from every mark; the Marks view switches it on. A block with the switch on is
  still listed before publishing and needs the author's confirmation.
- Hot spots are computed in the Data module (`data.aggregate.hotspots`: 120 m cells merged within
  150 m, as the hand-made reports did); Reports adds presentation only.
- **Keep this view**, a button under the map on the canvas, stores the frame readers see;
  **Show all the answers** clears it.
- The page, the embed, the PDF, the PNG and the CSV draw the same payload. The report file carries
  a map's view and frame, and a cross-tab's display settings, which a copy used to lose.

## Capabilities

### Modified Capabilities
- `reports-live-blocks`: a map block is drawn as its author chooses, framed by its author; the
  marks switch covers heat and hot spots made of every mark.

## Impact

`data/aggregate.py`, `reports/story.py`, `reports/render.py`, `reports/services.py`,
`reports/editor_views.py`, `reports/files.py`, `reports/tables.py`, `reports/pdf.py`,
`reports/drafting.py`, `reports/templates/reports/_block.html`, the editor's `_block_panel.html` and
`_canvas_block.html`, `js/public_results_render.js`, `js/report_builder.js`, `css/report_public.css`,
`css/report_builder.css`; tests in `survey/tests/test_reports_live_blocks.py`; help page; catalogs.

Not in this change: several questions on one map, a context layer from Data, view and frame through
REST / MCP.
