## Why

The client's site gets a screenshot of the map, and charts are pasted into slides as pictures
without their numbers. Issue #708 (epic #712).

## What Changes

- **Embed a report or one block** on another site: the survey embed mechanism reused — the
  response is marked framable by the report's allowed hosts (`Report.embed_allowed_hosts`, empty =
  any site), the framed page posts its height and `/embed.js` grows the iframe. A block has a page
  of its own, `/r/<slug>/block/<id>/`. Only a published public or unlisted report is framable.
- **oEmbed** for report and block links, with discovery on the page.
- **The numbers of a block as CSV**, from the block's payload, so masked exactly as the page:
  public at `/r/<slug>/block/<id>/data.csv` under the page's own guard, and in the editor for an
  unpublished report.
- **A block as PNG** with its title and caption, drawn by Pillow (charts as bars, a cross-tab as
  its table, a map as the static basemap with cells or marks) — in the editor.
- **All of them as one ZIP**, made on the worker like the PDF (`ReportPdf.kind = 'zip'`).

## Capabilities

### New Capabilities
- `reports-embed`: framing a report or a block, oEmbed, the per-block CSV and PNG, the ZIP.

### Modified Capabilities

None.

## Impact

- New `reports/embed.py`, `reports/tables.py`, `reports/pictures.py`; `reports/models.py`
  (+ `reports/0007`), `reports/views.py`, `reports/services.py`, `reports/tasks.py`,
  `reports/editor_views.py`, `survey/views.py` (`oembed`), `survey/urls.py`,
  `public_results.html`, `editor/public_results.html`.
- Not here: a "Report" block for Sites and the "used by a Site" line — that is a block kind of the
  Sites module (form, cleaner, template) and is filed as a follow-up; a Site can embed a report
  today only as any other site would, with the code.
