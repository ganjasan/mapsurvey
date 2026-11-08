## 1. Server

- [x] 1.1 `landing_views`: `autosave=1` → JSON for block edit and settings (fragments `_canvas_block.html`, `_outline_item.html`, hero); add creates a block from the kind alone with default data; new `editor_landing_block_duplicate`; `?select=<id>`
- [x] 1.2 `landings.page_blocks`: skip incomplete blocks (empty text, no files, no area, no question, no date); `clean_block` tolerates defaults under `creating=True`
- [x] 1.3 Canvas/panel context: per-block `card`, `payload`, errors, posted values; `is_editable`

## 2. Templates and assets

- [x] 2.1 `landings/editor/_canvas_block.html` (shell + editable marks per kind), `_outline_item.html`, `_panel.html` (page + per-block), `_library.html`
- [x] 2.2 `builder.html`: top bar (back, title, badge, device toggle, saved indicator, Preview, Publish popover), rail, canvas, panel
- [x] 2.3 `landing_builder.js`: selection, panel swap, Quill bubble on rich fields, plaintext contenteditable, debounce + blur autosave, fragment swap, errors, Sortable on canvas + outline, library, device toggle, publish popover
- [x] 2.4 `landing_builder.css` rewrite; `landing_public.css` reused inside the canvas frame

## 3. Verify

- [x] 3.1 Tests: autosave JSON ok / 422, incomplete blocks off the page, every kind renders editable, read-only canvas, duplicate; existing builder tests updated to the new markup
- [x] 3.2 Help page: builder paragraphs and screenshot; translations for new strings
- [x] 3.3 Full suite, validate, dev check with screenshots at 1440 and 390 px
- [ ] 3.4 PR into `epic/landing-pages`, merge
