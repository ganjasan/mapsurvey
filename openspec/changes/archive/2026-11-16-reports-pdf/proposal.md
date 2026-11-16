## Why

The council's clerk needs a paper for the meeting pack. Today the PDF of a report is made by hand
from the kit. Issue #707 (epic #712).

## What Changes

- **An A4 PDF of a report** (`reports/pdf.py`): the page's own payload laid out by reportlab — the
  opening, headings, text, pictures, key numbers, quotes, bar charts, the cross-tab, engagement,
  and maps with their basemap — with the report's address, the date and the page number in the
  footer. A block is never split across pages and a heading stays with what follows it.
- **Rendered on the worker, never in a web request**: the editor's "PDF (A4)" button creates a
  `ReportPdf` row, the Celery task renders and stores the file on the private media tier, the
  page polls and opens it.
- **A frozen report's PDF is rendered once and reused**, and its published page links to it; a
  live report's PDF shows the numbers of the moment it was asked for.
- Event `report_pdf_downloaded` (surface: editor | page).

## Capabilities

### New Capabilities
- `reports-pdf`: the document, the job, the stored file of a frozen report, who may download it.

### Modified Capabilities

None.

## Impact

- New `reports/pdf.py`, `reports/tasks.py`; `reports/models.py` (`ReportPdf`, migration
  `reports/0006`), `reports/services.py` (`request_pdf`, `ready_pdf`, `pdf_stamp`),
  `reports/views.py` (`report_pdf`, `report_page_pdf`), `survey/urls.py`,
  `editor/public_results.html`, `public_results.html`, `survey/product_events.py`.
- Uses `survey.print` (fonts, the static-map basemap) — no new dependency, no headless browser.
- Not here: a PDF made automatically at freezing (it would put a map download into every freeze),
  the Council paper's numbered-page look, a PDF preview pane.
