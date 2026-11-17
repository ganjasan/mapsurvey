## Context

Sites has a canvas builder (`sites/builder.html`, `js/site_builder.js`, `css/site_builder.css`,
changes landing-builder-redesign and landing-inline-editing): the public block templates inside an
editor shell, text marked `data-field` editable in place, each block's WHOLE form in a hidden pane
of the right panel, one autosave post per block answered with re-rendered fragments
(`block`, `outline`, `panel`). The report editor is `editor/public_results.html`: a form in the
centre and an iframe of `public_results.html` on the right, which is a standalone document with an
inline stylesheet and generic class names (`.row`, `.block`, `.wrap`).

## Goals / Non-Goals

**Goals**
- One builder for reports that looks and behaves like the Sites builder.
- No second builder script: the report builder runs on `site_builder.js`.
- The canvas draws blocks with the SAME markup and styles as `/r/<slug>/`.
- Every existing endpoint keeps its URL name and its non-AJAX behaviour (tests, API surfaces and
  deep links `?block=<id>` keep working).

**Non-Goals**
- New block kinds, the Data / Style / Annotate tabs of mockup S3, AI captions.
- Translating a report (the editor writes `en`, as before).
- Changing what readers see.

## Decisions

1. **Reuse `site_builder.js` as is, plus `report_builder.js` for what only a report has.**
   The Sites script already does selection, in-place text, Quill, rows (`data-rows`), file drops,
   panel-form autosave, reorder, the library and the device toggle through `lb-*` hooks. Three
   small changes to it: result payloads are also found by `script[data-results]` (not only in a
   `data-kind="results"` block), `plainValue()` returns `data-raw` for a field that shows a live
   number, and the opening is not swapped while another save is queued (a race that lost text
   typed in a second field — in Sites too). `report_builder.js` adds the publish dialog, PDF polling, the slug button, half-width
   pairing and the library's parameter forms. *Alternative*: a forked builder script — rejected,
   two builders drift.

2. **One block partial, `reports/_block.html`**, included by `public_results.html` and by the
   canvas for every block that shows data. The blocks the author writes (heading, text, picture,
   key numbers, quotes) are a dozen lines each and are drawn by the canvas block itself with the
   same classes plus the `data-field` / `data-rows` / `data-file` hooks. Styles move to `css/report_public.css`, every rule scoped under `.rp` (the public
   `<body class="rp">`, the canvas frame) and the row class renamed `rp-row` — the canvas lives
   under Bootstrap, whose `.row` is a negative-margin flex row.

3. **The canvas shows every block, live.** `reports/canvas.py::items(report)` builds one record per
   block (an autosave answer builds only the saved block's, `item_for`) with `ReportService._build_block` (uncached, hidden blocks included): payload, label, icon,
   type name and a `note` when readers do not see it (hidden / empty / question gone). A frozen
   report's canvas still shows the current blocks, with a notice that readers see the snapshot.
   The old iframe showed the snapshot and so hid every edit until "Update snapshot".

4. **Autosave contract = Sites'**. `block_edit` answered `{ok, block_id}` to XHR; with `autosave=1`
   it also returns `block`, `outline`, `panel` fragments. `save_settings` with `autosave=1` returns
   `title`, `public_url`, `hero`. Key numbers and quotes post parallel lists (`value`/`label`,
   `text`/`source`) from the row sink; the `items` textarea dialect stays accepted.

5. **Titles.** A question block's `<h2>` is editable; empty means "the question's name", shown as
   the placeholder in the title's own colour — typing nothing never writes the question name into
   `custom_title`.

6. **Half-width pairs** are a rendering rule (`story_rows`). On the canvas the block list is flat
   and sortable, so pairing is CSS (`.lb-item.rb-half` in a wrapping flex row) recomputed in the
   browser after a move or a width change with the same rule as `story_rows`.

7. **Add at a position**: `block_add` takes `after` (`top`, a block id or empty = end) and
   renumbers through `reorder_blocks`. A picture block may be created empty
   (`add_image_block(image=None)`); it is not rendered for readers until it has a file, which is
   what `_image_payload` already does.

8. **Base template**: `editor_base.html`, not `base.html` as Sites. Through a survey the builder
   IS that survey's Public results tab, and every page of a survey carries the survey's title
   (renamed in place), its tab strip and the publishing widget — existing tests hold all of them
   to it. `editor_base.html` also already loads Quill, SortableJS, Leaflet, HTMX and the comments
   drawer. The tab's own status line (state chip + actions) becomes the builder's top bar.

## Risks / Trade-offs

- Every block's panel form is in the page (as in Sites) → a 50-block report renders 50 small
  forms. Acceptable: Sites does the same; map popup fields are fetched in one query.
- Live rendering of every block on each open (no 60 s cache) → the same cost the preview iframe had
  after every edit, since the cache key carries `updated_at`.
- The mobile three-pane navigation of the Public results tab is dropped → the builder's own narrow
  layout (canvas above the panel) replaces it; the bottom bar keeps working on the other tabs.
- `public_results.html` loses its inline stylesheet → `collectstatic` is needed in worktrees;
  the embed and single-block pages use the same file.

## Migration Plan

No data change. Rollback = revert the commit.
