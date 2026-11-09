## Why

The owner asked how to put a heading of a chosen size on a site, or text without a heading. A block's heading was always one size and always a menu link; the only other way was Heading 1/2/3 inside a text block, which gave the page a second `<h1>` and an unstyled one. An empty heading slot looked required.

## What Changes

- New block kind **Heading**: the words on the canvas, a size in Settings (large, medium — `<h2>`; small — `<h3>`), first in the library.
- Every block gets **Show the heading in the menu at the top** in Settings (`SiteBlock.in_menu`, default on).
- The text block's toolbar offers **Heading / Subheading** (`<h2>` / `<h3>`, styled on the public page); an `<h1>` posted in a text body is stored as `<h2>` — the site title is the page's only `<h1>`.
- The empty block heading reads "Heading (optional)", paler.

## Capabilities

### Modified Capabilities
- `survey-sites`: block kinds gain Heading; headings can stay out of the menu; heading levels on a site.

## Impact

`survey/sites.py`, `site_views.py`, `models.py` + migration `0121_site_heading_block` (additive, `db_default`), templates `sites/blocks/heading.html`, `_canvas_block.html`, `_block_form.html`, `public.html`, `builder.html`, CSS, `js/site_builder.js`, help, catalogs.
