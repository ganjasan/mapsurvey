## 1. One look for the page and the canvas

- [x] 1.1 Move the block markup of `public_results.html` into `reports/_block.html` (`editing` adds the in-place hooks)
- [x] 1.2 Move the page's styles into `css/report_public.css`, scoped under `.rp`, row class `rp-row`
- [x] 1.3 Public page, embed and single-block pages render as before (existing tests)

## 2. Server

- [x] 2.1 `reports/canvas.py`: one record per block (payload, label, type name, icon, note)
- [x] 2.2 `_config` renders `reports/builder.html`; `?block=` / `?select=` select a block
- [x] 2.3 `block_edit` with `autosave=1` answers block / outline / panel fragments; rows as parallel lists
- [x] 2.4 `save_settings` with `autosave=1` answers title, public URL and the opening fragment
- [x] 2.5 `block_add`: `after` position; a picture block without a file
- [x] 2.6 `block_delete` returns to the builder; delete through the confirmation dialog

## 3. Builder

- [x] 3.1 `reports/builder.html`: top bar, outline, canvas, panel, library, publish dialog
- [x] 3.2 Canvas block shell, opening, outline row, block pane, page pane
- [x] 3.3 `site_builder.js`: result payloads by `script[data-results]`, `window.LB` hooks
- [x] 3.4 `report_builder.js` + `report_builder.css`: publish, PDF, slug, pairs, library forms
- [x] 3.5 Comments drawer and badges on the canvas for a report with a home survey
- [x] 3.6 Remove `editor/public_results.html`, `pr_add_block_modal.html`, `pr_block_list_item.html`

## 4. Tests, strings, docs

- [x] 4.1 Tests for the new requirements in `survey/tests/test_reports_editor.py`
- [x] 4.2 New creator strings in every offered catalog
- [x] 4.3 Help page of the report editor and CLAUDE.md paragraph
- [x] 4.4 Screenshots of the builder on a made-up report
