## Why

Issue #606 (epic #348, Sites v1.1 wave A, story S10). Every project site names the people behind it and how residents reach them; today a creator has to fake it with a text block.

## What Changes

- New block kind **Contacts**: up to six people (name, role, e-mail, phone) added and edited as rows in the block on the canvas; address and opening hours in Settings.
- Public page: cards with `mailto:` and `tel:` links; a row without a name is not drawn; a malformed e-mail is refused (an empty one is fine).

## Capabilities

### Modified Capabilities
- `survey-sites`: the closed set of block kinds gains `contacts`.

## Impact

`sites.py` (kind, cleaner, `is_complete`), `site_views.py` (`_raw_block`), migration `0123` (choices only), templates `blocks/contacts.html`, `_inline.html`, `_block_form.html`, `_canvas_block.html`, CSS, help, catalogs.
