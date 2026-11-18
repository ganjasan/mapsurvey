## 1. Server

- [x] 1.1 `story.clean_config('crosstab')`: `view`, `values`, `sort`
- [x] 1.2 `services.set_crosstab_questions`, `services.set_compare`; `update_block(crosstab_display=)`; new cross-tab blocks start as bars
- [x] 1.3 Library tiles one click with defaults; `_block_add` fills them; `_block_edit` reads the panel
- [x] 1.4 `render`: bars / stacked / ranking / table from the payload, groups left out named

## 2. Editor and page

- [x] 2.1 Panel Data section for cross-tab and compare (selects, view tiles, values, sort)
- [x] 2.2 `_block.html` + `report_public.css` draw the views
- [x] 2.3 Library forms removed

## 3. Tests and catalogs

- [x] 3.1 Tests in `test_reports_live_blocks.py`, `test_reports_reuse.py`
- [x] 3.2 Catalog entries
