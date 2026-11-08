## Why

The builder shipped with #576 is a list of collapsed rows, each hiding a form behind "Edit",
with page settings stacked in a side column. The owner's verdict on 2026-11-08: "очень не
нравится". Every current page builder (Tilda, Squarespace Fluid Engine, Notion-style editors,
Maptionnaire Project Pages) converges on one shape — the page itself is the editor — and the
mockup in this folder (`builder.mockup.html`, approved by the owner) follows it. Issue #594,
epic #348.

## What Changes

- **Canvas**: the builder renders the page as `/p/<slug>/` does, block by block, through the
  same block templates. Headings, text bodies, captions and descriptions are edited in place
  (Quill in bubble mode for rich text: a floating B / I / link / list toolbar on selection).
- **Hover toolbar** on every block: drag handle, move up / down, duplicate, settings, delete.
  A "+" line between blocks and under the last one opens the block library (categories *Tell
  the story* / *Take part* / *Show the work*, icon + one-line description, search).
- **Left rail**: the page outline — one row per block with its kind icon and heading, click
  to scroll and select, drag to reorder, an orange dot on a survey card whose survey is a
  draft or on a results block whose question is gone.
- **Right panel**: the settings of the selected block (everything that is not text: survey,
  phases, files, map options, event dates, viz), or the page settings (cover, address,
  language, visibility, surveys on this page) when nothing is selected.
- **Autosave**: every change posts after a short debounce with `autosave=1` and gets JSON
  back — the re-rendered block, its outline label, or field errors shown in the panel. A
  "Saving… / Saved just now / Could not save" indicator sits in the top bar. No Save buttons.
- **Publish popover** on the top bar: the address with Copy, listed / unlisted switch, QR
  download, *Publish now* / *Unpublish*; the status badge next to the title.
- **Desktop / phone toggle** reflows the canvas to 390 px.
- Add and delete stay full posts that return to the builder (selecting the new block); every
  other write is JSON.

## Capabilities

### Modified Capabilities
- `survey-landings`: the requirement "A landing is a workspace-owned public page" gains the
  builder's shape (canvas, in-place editing, autosave, outline, panel, publish popover); block
  validation is unchanged.

## Impact

- Rewritten: `survey/templates/landings/builder.html` (+ new partials
  `landings/editor/_canvas_block.html`, `_panel.html`, `_outline_item.html`, `_library.html`),
  `survey/assets/js/landing_builder.js`, `survey/assets/css/landing_builder.css`.
- Changed: `survey/landing_views.py` (JSON answers under `autosave=1`, fragment rendering,
  duplicate endpoint), `survey/urls.py` (duplicate), tests, help page screenshots/wording.
- Unchanged: models, `landings.clean_block`, the public page, permissions, the Pro gate.
- Removed: the `_block_form.html`-as-row layout and per-block Save buttons; `_block_form.html`
  becomes the panel's settings form (text fields that moved to the canvas leave it).
