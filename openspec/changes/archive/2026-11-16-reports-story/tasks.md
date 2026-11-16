## 1. Story blocks and the reader page

- [x] 1.1 `ReportBlock.config`, `width`, block types `heading | numbers | quotes`; migration `reports/0003`
- [x] 1.2 `reports/story.py` (clean_html, clean_config, lines ↔ items); services `add_story_block`, `update_block(width=, items=)`, eyebrow in settings
- [x] 1.3 `reports.render`: payloads of the new blocks, `html` for text, `story_rows`
- [x] 1.4 `public_results.html` as a story: opening, rows, half-width pairs, numbers, quotes; works without a home survey

## 2. The editor by report

- [x] 2.1 `on_survey` / `on_report`, `_urls`, `may_edit_report`; routes `editor/reports/<uuid>/…`
- [x] 2.2 editor template: URLs from `u`, navbar without a survey, forms of the new blocks, Quill for text, width
- [x] 2.3 Reports list: links to the editor, New report, Import; delete page

## 3. The report file

- [x] 3.1 `reports/files.py`: export, import with re-binding and notes
- [x] 3.2 views `report_export`, `report_import`, `report_delete`
- [x] 3.3 ops: `scripts/report_html_to_file.py`; the first hand-made report imported on a dev server

## 4. Ship

- [x] 4.1 tests: `test_reports_story.py`, `test_reports_editor.py`, `test_reports_import_export.py`
- [x] 4.2 help page, CLAUDE.md
- [x] 4.3 validate, archive (the test lineage needs the specs), touched modules, full suite, screenshots, PR into `epic/reports`
