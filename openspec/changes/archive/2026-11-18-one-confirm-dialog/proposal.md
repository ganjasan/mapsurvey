## Why

The creator app asked "are you sure?" in five different ways: the editor's dialog (`#editorDialog`,
`Dialog.confirm`), a second dialog for Sites and the report builder (`#lb-confirm`), two standalone
confirmation PAGES (delete a report, delete a dataset), and thirteen browser `confirm()` boxes
(billing, members, API tokens, map styles, paper responses, share links, restore a version,
publishing with translation gaps, trashing a response). On pages extending `base.html` the editor's
dialog script was loaded without its markup, so it silently fell back to the browser box. The owner
asked for one style (2026-11-18).

Separately, the owner asked to take the four draft arrangements off the report start page for now
and concentrate on the blank report.

## What Changes

- ONE dialog, `partials/_app_dialog.html`, included by both base templates and driven by
  `js/editor_dialog.js`: `Dialog.confirm()` / `Dialog.alert()` from script, `data-confirm` on a form
  from markup (title, optional body, muted note, action label, `data-confirm-tone="primary"` for an
  action that destroys nothing), and every `hx-confirm`.
- The Sites-only dialog (`sites/editor/_confirm_modal.html`, `js/site_confirm.js`) is removed; its
  forms keep their `data-confirm` attributes.
- Deleting a report and deleting a dataset ask through the dialog; the two confirmation pages are
  removed (a GET of their old address opens the report / the dataset and deletes nothing).
- Every browser `confirm()` in creator templates becomes the dialog.
- Reports: "New report" creates a blank report in one click. The start page offers the blank report
  only; the arrangements drafted from a survey and "Copy an earlier report" are off the page (the
  view, the API and MCP keep the drafting code).

## Capabilities

### Modified Capabilities

- `reports-editor`: a report is deleted through the dialog; new requirement for the one dialog.
- `reports-start`: the start page offers the blank report only; "New report" is one click.
- `data-links`: deleting a dataset asks on the dataset's page, where the places are listed.

## Impact

- `survey/templates/partials/_app_dialog.html` (new), `base.html`, `editor/editor_base.html`,
  `js/editor_dialog.js`; removed `sites/editor/_confirm_modal.html`, `js/site_confirm.js`,
  `reports/delete.html`, `data/delete.html`.
- `reports/views.py`, `reports/models.py` (`Report.is_home`), `reports/_delete_confirm.html`,
  `reports/list.html`, `reports/start.html`, `reports/editor/_page_panel.html`.
- `data/views.py`, `data/dataset.html`.
- Templates with inline confirms: billing, org members, map styles, API connections, paper response
  slots, share links, publishing widget, lifecycle scripts, Responses table engine, abuse review.
- No new translatable strings: the dialog reuses the sentences of the removed pages and confirms.
