## 1. Shared rules

- [x] 1.1 `reports.sources.popup_subquestions(question_ids)` (moved from `editor_views._geo_subquestions`; the editor imports it)
- [x] 1.2 `services.layer_refusal(block, layer, seen)`; `_checked_layers` uses it

## 2. Blocks from plain values

- [x] 2.1 `reports.blocks._map_settings(block, spec)`: view/opts/colour/name/frame/legend/scale/toggle, layers (names, ids, default view, survey), hot spots only for point questions, popup fields, basemap, Marks view vs `show_marks: false`
- [x] 2.2 `_common` passes `map_display`, `geo_label_fields`, `basemap`; crosstab `display` → `crosstab_display`
- [x] 2.3 Module docstring lists the new keys

## 3. REST and MCP

- [x] 3.1 `MapOptsIn`, `MapLayerIn` (aliases `code`/`marks`/`fields`), `CrosstabDisplayIn`; fields on `BlockIn` and `BlockPatchIn`
- [x] 3.2 MCP descriptions of `add_report_block` / `update_report_block`
- [x] 3.3 Regenerate `reference/api.md` and `reference/mcp-tools.md`

## 4. Tests (`survey/tests/test_reports_usage_api.py`)

- [x] 4.1 Rebuild a two-layer map; round trip of `layers`; `frame: null`
- [x] 4.2 Strict refusals, each leaving the block unchanged
- [x] 4.3 Cross-tab display
- [x] 4.4 MCP `update_report_block` with nested opts
- [x] 4.5 Run `survey.tests.test_reports_usage_api`, the report editor tests, `api`, `mcp`
