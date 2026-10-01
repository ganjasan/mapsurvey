# story_tools — pictures for a customer story (skill `customer-story`)

Three small scripts, run from a scratch directory that holds `data/` (CSV exports from the prod
DB) and gets `maps/`, `shots/` written next to it. They are working copies of the tools used for
the Remington and Pszów stories; adapt the data section of `story_maps.py` per story (question
codes, colours, bounds).

1. `story_maps.py` — builds Leaflet pages (`maps/<name>.html`) with heat layers (leaflet.heat,
   one hue per question, marks never drawn as points) and reference layers (from the layer's
   `geojson_gz`, base64 in the CSV). OpenStreetMap tiles. Serve `maps/` with
   `python3 -m http.server 8421`.
2. `story_map_shots.py [names…]` — screenshots each page's `#map` (1000×760 @2x) with headless
   Chromium: `env/bin/python story_map_shots.py remington-value`.
3. `story_phone_shots.py <locale> [goto=<url>] [click=<text>] [js=<code>] name=<url|shot> …` —
   390×844 @2x phone frames of the survey on the worktree dev stand (never the live survey);
   removes the debug toolbar before every click/shot; `js=toggleInfo(false)` collapses the panel.

Exports that feed them (psql `\copy`): points as `code, lat, lon`; mixed geometry as
`code, input_type, ST_AsGeoJSON(...)`; layers as `id, name, color, encode(geojson_gz,'base64')`.
