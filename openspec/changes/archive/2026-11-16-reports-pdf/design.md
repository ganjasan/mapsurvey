## Context

The issue leaves the renderer to design with one condition: it must draw the maps. The project
already prints surveys with reportlab (`survey/print/pdf.py`), with registered Unicode fonts and a
static-map module that fetches a Mapbox Static Images basemap and paints over it with Pillow. A
headless browser would draw the page as it is but needs Chromium on the web image, hundreds of MB
of memory per render, and was the kind of process behind the 2026-09 incidents.

## Decisions

1. **reportlab, not a headless browser.** The PDF is laid out from the payload
   (`reports.render.build_context`), block by block. Cost: the PDF is a document in the report's
   order and typography, not a pixel copy of the web page. Gain: no new dependency, tens of MB,
   and the same fonts and static maps the printed form uses.
2. **The payload is the contract.** `reports/pdf.py` reads `rows` exactly as the template does and
   never queries answers; "the numbers equal the page" holds by construction, masked values
   included. A new block type needs a branch in `_block`, like a branch in the template.
3. **Maps = static basemap + Pillow.** The extent of the block's cells (or marks) picks the zoom;
   cells are painted with opacity by respondents, marks as dots, lines and outlines. A failed
   basemap fetch degrades to a plain ground.
4. **Blocks are kept together** (`KeepTogether`), and a heading is folded into the block after it,
   so the issue's "page breaks shown in Preview" needs no check: nothing splits. A block taller
   than a page is the one case reportlab splits by itself.
5. **A row per rendering, `ReportPdf`**, with a `stamp`: `frozen:<frozen_at>:<updated_at>` — one
   stored PDF per snapshot, reused — or `live:<now>`, a new one each time. Three newest per report
   are kept. Files sit on the private tier and are served only through the two views.
6. **The task claims the row** (`filter(status='queued').update(status='running')`), so a
   redelivered message does nothing — the import job's rule.
7. **No PDF at freezing time.** Rendering on every freeze would put a map download and a worker
   job into an action people use casually; the author presses "PDF (A4)" once and the page then
   links it.
8. **Without a broker (local dev) the task runs inline** — the pattern `data.services._enqueue`
   uses; on Render the broker exists and the web process only enqueues.

## Risks / Trade-offs

- [A very long report holds its pictures in memory on the worker] → JPEG at 86 %, pictures scaled
  to the column; the worker recycles.
- [The PDF's look differs from the page's] → same order, same numbers, same words; charts are bars
  in both.

## Migration Plan

`reports/0006`: `ReportPdf`. Rollback: revert; stored files are orphaned keys on the private tier.
