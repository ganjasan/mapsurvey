## 1. Readers and tags

- [x] 1.1 `ReportUsage` + `reports/usage.py` (`count`, `summary`); counted in `report_page`, `report_block`, `report_page_pdf`
- [x] 1.2 Readers card in the editor's Settings
- [x] 1.3 `Tag.reports`, `data.tags` relation, `services.update_settings(tags=)`, Settings field, list badges and filter

## 2. API and MCP

- [x] 2.1 `reports/blocks.py` (spec → services), `files.entry_of`, `services.delete_report`
- [x] 2.2 `api/v1/reports.py` and its registration
- [x] 2.3 `mcp/tools/reports.py`
- [x] 2.4 regenerate `reference/api.md` and `reference/mcp-tools.md`

## 3. Ship

- [x] 3.1 tests `survey/tests/test_reports_usage_api.py`
- [x] 3.2 help guide, What's new hero for the epic, CLAUDE.md
- [x] 3.3 validate, archive, full suite, PR into `epic/reports`
