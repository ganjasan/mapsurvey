## Why

Issue #621 (epic #348, Sites v1.1 wave B, story S9). Landscape and design firms communicate with pictures: concept boards, renderings, site photos, and "today vs the proposal". One picture per Image block made a set of boards a long scroll (the Remington demo needed three Image blocks and three headings).

## What Changes

- **Gallery** block: up to 12 pictures (verified by their bytes, stored as `SiteFile` rows like documents), captioned in the block, 2–4 columns (two on a phone), a lightbox (`js/site_media.js`, a `<dialog>`; links to the files without script).
- **Before and after** block: two pictures in slots 0/1, dropped or replaced in their half of the block, labels per slot, a slider over the two pictures (`clip-path`; one under the other without script).
- Both honour Full width; captions and labels are translatable; uncaptioned gallery pictures are flagged by the accessibility checks.
- The documents upload path becomes `_file_changes` (files or pictures).

## Capabilities

### Modified Capabilities
- `survey-sites`: two new block kinds.

## Impact

Migration `0128` (choices only); `sites.py`, `services/sites.py`, `site_translations.py`, `site_views.py`; templates `blocks/gallery.html`, `blocks/compare.html`, `_inline.html`, `_block_form.html`, `_canvas_block.html`, `public.html`, `builder.html`; `js/site_media.js`; CSS; help; catalogs.
