## Why

Issue #605 (epic #348, Sites v1.1 wave A, story S1). A landscape or planning firm cannot show a master plan or a rendering in the fixed 760 px column of a site: the drawing is unreadable. The owner found it on the dev stand.

## What Changes

- `Site.width` — narrow / standard / wide (760 / 960 / 1200 px) in Site settings → **Page width**; default narrow, so existing sites look as before. One CSS variable (`--lp-max`) drives the header, menu and blocks; the builder's canvas uses the same width.
- **Full width** switch in the settings of image, video and map blocks: the picture, the player or the map spans the page (up to 1400 px), the heading and caption stay in the column.
- No columns, grids or per-block layout (Vision §3.3 still holds).

## Capabilities

### Modified Capabilities
- `survey-sites`: a site has a page width; image, video and map blocks can be full width.

## Impact

Migration `0122_site_width` (additive, `db_default`), `sites.py` cleaners, `site_views.py`, templates `public.html`, `builder.html`, `_page_panel.html`, `_block_form.html`, `_canvas_block.html`, CSS, `js/site_builder.js`, help, catalogs.
