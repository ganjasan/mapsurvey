## 1. The document

- [x] 1.1 `reports/pdf.py`: styles, rich text, bars, series, tables, key numbers, map pictures, `build_pdf`
- [x] 1.2 tried on the made-up report and on the imported hand-made report (50 blocks, 18 pictures)

## 2. The job

- [x] 2.1 `ReportPdf` (migration `reports/0006`); `services.request_pdf`, `ready_pdf`, `pdf_stamp`
- [x] 2.2 `reports/tasks.py::render_report_pdf`
- [x] 2.3 views `report_pdf` (ask, poll, download) and `report_page_pdf`; the editor's button; the page's link; the event

## 3. Ship

- [x] 3.1 tests `survey/tests/test_reports_pdf.py`
- [x] 3.2 help, CLAUDE.md
- [x] 3.3 validate, archive, touched modules, full suite, PR into `epic/reports`
