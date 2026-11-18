## 1. Server

- [x] 1.1 `story.clean_config('map')`: `layers`, `color`, `name`, `opts`, `legend`, `scale`, `toggle`; `clean_map_look`, `map_opts`
- [x] 1.2 `render._map_layer` per layer; `layers`, `legend_rows`, `spot_lists` in the block's payload
- [x] 1.3 `services.update_block(map_display=)` takes the layers; `_checked_layers` refuses what is not a map question of the workspace
- [x] 1.4 `checks`: marks of any layer; report file and copy onto another survey; PDF / PNG paint every layer

## 2. Editor and page

- [x] 2.1 Panel: a card per layer (`_map_layer.html`), add and remove, legend / scale / readers' switch
- [x] 2.2 `public_results_render.js`: layers bottom to top, view settings, legend boxes
- [x] 2.3 `_block.html` legend and lists per layer

## 3. Tests, help and catalogs

- [x] 3.1 `MapLayersTest` in `test_reports_live_blocks.py`
- [x] 3.2 Help page, catalog entries
