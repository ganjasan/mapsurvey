## Context

Surveys are embeddable since `embed-surveys` (#284): `mark_embeddable` sets
`request.survey_frame_ancestors`, `SurveyEmbedMiddleware` turns it into `frame-ancestors`, the
framed page posts `{mapsurvey: "height"}` and `/embed.js` grows the iframe; `/oembed/` describes a
survey link. A report page is read-only and needs no cookies, so the cross-site cookie problems of
survey embeds do not apply. The PDF change added a worker job with a stored file.

## Decisions

1. **Reuse the mechanism, not copy it.** `reports.embed.mark` sets the same request attribute, so
   the same middleware applies it; the framed page posts the same message, so the same
   `/embed.js` (pasted once, never updated) serves both.
2. **An allow-list per report** (`Report.embed_allowed_hosts`, the survey's normaliser and
   `frame_ancestors`). Empty = any site, as for surveys: a report is published to be read.
3. **A block's page is the report's template with one row** (`single=True`: no opening). No second
   template to keep in step; the block's data comes from the same `render_data`, so a hidden or
   foreign block is simply absent → 404.
4. **CSV and PNG read the payload.** `reports/tables.py::rows_of(payload)` and
   `reports/pictures.py::block_png(payload)`: neither touches answers, so "the CSV never contains
   a group the page hides" holds by construction — the masked value is not in the payload.
5. **PNG by Pillow**, not a screenshot: bars for charts, the table for a cross-tab,
   `pdf.map_image` for maps. One PNG in the editor is drawn in the request (at most one basemap
   fetch with the static-map module's 5 s timeout and day-long cache — what the printed form does);
   the ZIP of all of them is a worker job, `ReportPdf` with `kind='zip'`.
6. **Public CSV, editor-only PNG.** A CSV is cheap and belongs next to an embed; a PNG costs a
   basemap fetch and is an author's tool.
7. **Sites.** A "Report" block for Sites is a block kind of the Sites module and is not built
   here; nothing in a report's data says a Site embeds it until that block exists, so the "used
   by" line waits for it.

## Risks / Trade-offs

- [`frame-ancestors *` on every public report] → the same exposure as a survey page; the report
  is read-only and carries no session.
- [Captions inside PNGs are English] → the title is the author's own text; fixed strings in
  pictures join the catalogs debt.

## Migration Plan

`reports/0007`: `Report.embed_allowed_hosts`, `ReportPdf.kind`. Rollback: revert.
