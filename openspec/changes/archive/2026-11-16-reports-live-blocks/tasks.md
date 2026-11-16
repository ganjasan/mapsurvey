## 1. Blocks

- [x] 1.1 block types `crosstab`, `engagement` (migration `reports/0004`); `services.add_view_block`
- [x] 1.2 `dataviews.result(view, lang, k)`; `render._view_payload`; table and funnel on the page
- [x] 1.3 map `config.marks`: payload of geometries, `renderMarks` in the client renderer, the editor's switch
- [x] 1.4 `reports/tokens.py`: tokens in text, key numbers and the opening; the frozen snapshot keeps them
- [x] 1.5 editor: add-block options and question pickers, block notes, token help
- [x] 1.6 report file: export and import of the new blocks and the switch

## 2. Ship

- [x] 2.1 tests `survey/tests/test_reports_live_blocks.py`, additions to `test_reports_import_export.py` and `test_public_aggregates.py`
- [x] 2.2 help, CLAUDE.md
- [x] 2.3 validate, archive, touched modules, full suite, screenshots on the made-up report, PR into `epic/reports`
