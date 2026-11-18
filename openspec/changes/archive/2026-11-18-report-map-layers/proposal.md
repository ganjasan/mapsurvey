## Why

A map of one question cannot carry an analysis. The maps of the reports made by hand put two
questions on one map — where it is too hot and where people cool down, the routes people walk and
the places that trouble them — and the reading is in how they overlap. The views of change
`report-map-views` also had no settings of their own: how wide the shading spreads, how many hot
spots are numbered, what counts as one place (#753, owner's review of the mockup board).

## What Changes

- A map block holds **layers**: its own question first, then up to three other map questions of
  the workspace, each named by survey and question code in `ReportBlock.config['layers']`. A block
  made before is a map of one layer.
- Each layer has its own **view**, **view settings**, colour, name in the legend, the sub-questions
  it sums up, and its own "Use every mark" switch. Heat: spread and strength. Hot spots: how many
  are numbered, what counts as one place (60 / 120 / 300 m), the list under the map, the shading
  under the numbers. Squares: automatic, finer or coarser. Marks: size, solid colour.
- The block has the basemap, the frame, a **legend** under the map, the scale bar, and a switch that
  lets readers turn layers off and on.
- The panel lists the layers as cards (one form, one autosave); a layer is added from a list of the
  map questions the author may see and removed from its card.
- Privacy is per layer: areas with at least K respondents unless that layer uses every mark; a
  layer that does is listed before publishing as the block's own is.
- The page, the embed, the PDF and the PNG draw every layer; the report file carries them, and a
  copy onto another survey reads that survey in every layer.

## Capabilities

### Modified Capabilities
- `reports-live-blocks`: a map block shows several questions as layers, each drawn with its own
  view and settings.

## Impact

`reports/story.py`, `reports/render.py`, `reports/services.py`, `reports/editor_views.py`,
`reports/checks.py`, `reports/files.py`, `reports/pdf.py`, `reports/templates/reports/_block.html`,
`_map_spots.html`, the editor's `_block_panel.html` and `_map_layer.html`,
`js/public_results_render.js`, `js/report_builder.js`, `css/report_public.css`,
`css/report_builder.css`; tests in `survey/tests/test_reports_live_blocks.py`; help page; catalogs.

Not in this change: context layers from Data (a boundary, existing objects), areas shaded by
answers, a filter by sub-question, reordering layers, layers through REST / MCP.
