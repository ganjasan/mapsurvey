## 1. Embedding

- [x] 1.1 `Report.embed_allowed_hosts` (migration `reports/0007`); `reports/embed.py` (mark, snippet, hosts)
- [x] 1.2 the page in embed mode (no ribbon, height messages), the single-block page, oEmbed and its discovery link
- [x] 1.3 editor: the embed card with the allow-list, a block's own code

## 2. Numbers and pictures

- [x] 2.1 `reports/tables.py`: CSV from the payload; public and editor routes
- [x] 2.2 `reports/pictures.py`: PNG by Pillow; editor route
- [x] 2.3 ZIP as a worker job (`ReportPdf.kind`), the editor's button

## 3. Ship

- [x] 3.1 tests `survey/tests/test_reports_embed.py`
- [x] 3.2 help, CLAUDE.md, follow-up issue for the Sites block
- [x] 3.3 validate, archive, touched modules, full suite, PR into `epic/reports`
