## Why

The report editor that shipped with epic #712 is still the layout of the old Public results tab:
a list of blocks on the left, a settings FORM in the centre and the report in a preview iframe on
the right. The author writes a story in form fields and watches a small copy of it reload. The
board the epic was drawn from (screens S2 and S3) showed the opposite, and Sites already works
that way: the page itself in the centre, edited in place, with a context panel for the rest
(owner, 2026-11-17; #731).

## What Changes

- **The report is the canvas.** `/editor/reports/<uuid>/` and a survey's Public results tab open
  one builder: outline on the left, the report as readers see it in the centre, a context panel on
  the right. The preview iframe and the centre form are gone.
- **Editing in place**: the opening (line above the title, title, opening paragraph), headings,
  text (Quill toolbar on the page), key numbers and quotes row by row, a picture's file and
  caption, a map's description, a block's title.
- **The context panel** holds what is not text on the page: a selected block's further settings
  (visualisation, basemap, marks, popup fields, width, hidden, use elsewhere) or, with nothing
  selected, the report's settings (address, visibility, display and privacy, tags, embed, readers,
  file and PDF, data mode).
- **Block library**: "+" between blocks and "Add block" open one dialog; a story block is one
  click, a chart or a map is one click on its question, a new block lands where the "+" was.
  A picture block starts empty and takes its file on the page.
- **Block toolbar on the page**: drag, move up / down, comment, settings, delete (the app's
  confirmation dialog, not `confirm()`).
- **A block that readers do not see** (hidden, not filled in, question deleted) stays on the canvas
  with a note saying why.
- The builder reuses the Sites builder's script and stylesheet (`site_builder.js`,
  `site_builder.css`); the report page's styles move from the inline `<style>` of
  `public_results.html` to `css/report_public.css`, shared by the public page and the canvas.
- **BREAKING (creator UI)**: the three-pane screen `editor/public_results.html` is removed; its
  status line (state chip and actions) becomes the builder's top bar, and its mobile
  Structure / Edit / Preview panes go (the builder follows Sites below 760 px: canvas, then
  panel). The survey's title, tab strip and publishing widget stay above the builder.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `reports-editor`: the editor is a canvas with a context panel; adding, placing, writing and
  moving blocks happen on the page.

## Impact

- `reports/editor_views.py` (builder context, autosave answers with fragments, add at a position),
  new `reports/canvas.py`, `reports/services.py` (empty picture block, position).
- New templates `reports/templates/reports/builder.html` and `reports/editor/*`; removed
  `survey/templates/editor/public_results.html`, `editor/partials/pr_add_block_modal.html`,
  `pr_block_list_item.html`.
- `survey/templates/public_results.html` → block markup in `reports/_block.html`, styles in
  `survey/assets/css/report_public.css`.
- `survey/assets/js/site_builder.js`: two small generalisations (result payloads by attribute,
  optional hooks); new `survey/assets/js/report_builder.js`, `css/report_builder.css`.
- Translation catalogs: new creator strings in all offered languages.
- No model change, no migration, no API or MCP change.
