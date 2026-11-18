## 1. Server

- [x] 1.1 `data.aggregate.hotspots` (120 m cells, 150 m merge, K respondents or every mark)
- [x] 1.2 `story.clean_config('map')`: `view`, `marks`, `frame`; `story.map_view`
- [x] 1.3 `services.update_block(map_display=)`; new map blocks start as heat (editor, draft, scaffold)
- [x] 1.4 `render._map_payload`: `display`, `frame`, `hotspots`, `k`
- [x] 1.5 Report file keeps view and frame (and a cross-tab's display); CSV of hot spots; PDF / PNG heat, badges, frame

## 2. Editor and page

- [x] 2.1 Panel: view tiles, "Use every mark"
- [x] 2.2 Canvas: "Keep this view" / "Show all the answers"
- [x] 2.3 `public_results_render.js`: heat, hot spots, frame, scale; `_block.html` list and legend

## 3. Tests, help and catalogs

- [x] 3.1 `MapViewsTest` in `test_reports_live_blocks.py`
- [x] 3.2 Help page, catalog entries
