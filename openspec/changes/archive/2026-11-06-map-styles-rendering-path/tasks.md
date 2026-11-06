## 1. Setup

- [x] 1.1 Register offset 760 → `Mapsurvey-map-styles-render` in `.env.ports.example`; seed the dev stack with `seed_demo_survey` (Copenhagen) and confirm Paper A renders on the respondent page as it does on master
- [x] 1.2 Secret token: the existing `MAPBOX_STYLES_TOKEN` in `.env` (styles:list confirmed against the account); never in a template, never committed
- [x] 1.3 Store a copy of the `streets-v12` base style JSON under `survey/tests/fixtures/mapbox_streets_v12.json` (fetched once with the server token; it is the fixture the pure-function tests run on)

## 2. Publishing script (deliverable)

- [x] 2.1 `scripts/mapbox_style_publish.py`: `load_settings(path)`, `apply_settings(style, settings)` (pure; `poi`, `buildings`, `labels`, `place_names`, `park_color`, `water_color`, `road_contrast`, `greyscale`), `MapboxStylesClient` (`get_base`, `find_by_name`, `create`, `update`, `delete`, `static_url`), `main()` that prints the style id and a Static Images check-frame URL
- [x] 2.2 Reproduce Paper A from a settings file (`scripts/map_styles/paper_a.json`) and diff the result against the hosted Paper A's JSON; record any hand edits the script does not cover
- [x] 2.3 Reproduce Paper B the same way (`scripts/map_styles/paper_b.json`)
- [x] 2.4 `survey/tests/test_map_style_rendering.py`: the four script scenarios of the spec (idempotent name, `poi` toggle round-trips, greyscale colours, token only from `MAPBOX_STYLES_TOKEN` and absent from templates); add the module to the spec lineage (new capability, new module)
- [x] 2.5 Limits: create throw-away styles in a loop until the API refuses or 50 are made; record the count, the rate-limit headers, then delete them all; confirm the account lists only Paper A, Paper B and `print-check` afterwards
- [x] 2.6 Freshness: create a style, request a Static Images frame immediately and at +30 s, +2 min; update its park colour, poll a raster tile and a Static Images frame (`fresh=true` and without) until each shows the change; record the delays

## 3. Prototype A — vector on the client

- [x] 3.1 Read the current Mapbox Vector Tiles API terms on third-party renderers; record the finding in the ADR appendix. If MapLibre is not permitted, use Mapbox GL JS v3 for A and note the per-load price
- [x] 3.2 On the branch only: `?basemap_proto=vector` under `DEBUG` makes `basemap_layers.html` include MapLibre GL + `maplibre-gl-leaflet` and add `L.maplibreGL({style})` as the base layer, with the Paper A style JSON (sources rewritten to the token) served from a dev-only view
- [x] 3.3 Walk the respondent flow on desktop and phone: point/line/polygon/spray placement, crosshair, reference layers, layer switcher, popups, embedded page; list every behaviour that changed
- [x] 3.4 Check coordinate fidelity: place a point on a known landmark with raster and with vector, compare the stored coordinates; note any drift
- [x] 3.5 Measure at 1280×800 and 390×844, z15 city centre, two runs, CDN miss and hit: billable vector tile requests, bytes, first full render; phone numbers from a real Android device over Chrome remote debugging — *as done:* headless Chromium, phone = 390×844 DPR 3 with 4× CPU throttling; no real device (ADR caveats)
- [x] 3.6 Measure the editor loop: time from a style JSON change to the preview repainting (`map.setStyle` with diff)

## 4. Prototype B — hosted raster

- [x] 4.1 `?basemap_proto=raster` uses the script-published Paper A (from 2.2) as a `tiles/256` and a `tiles/512` layer (the #522 shape, `tileSize: 512, zoomOffset: -1`)
- [x] 4.2 Same measurements as 3.5 for both tile sizes; raster is the baseline the vision's cost line is written against
- [x] 4.3 Editor loop under B: time from a settings change through `PATCH` to a `fresh=true` Static Images preview, and to a raster tile showing the change (from 2.6) — *as done:* from the 2.6 probe; in-place PATCH never reaches tiles within 20 min, hence immutable styles (ADR decision 2)

## 5. Print for each path

- [x] 5.1 B: print the Copenhagen form with the script-published style; confirm `static_map.render_frame` and the reference image come from the same style id and that the pen-mark reader on a photographed page is not worse than on Paper A (reuse the #535 benchmark pages) — *as done:* print frame resolves to the hosted Paper A id, which the script reproduces layer for layer, so the reader sees the same image; no new benchmark run
- [x] 5.2 A: establish how a client-rendered style prints — Static Images from a hosted copy (so A still needs the script), or a server-side renderer; name the option and its cost, do not build a renderer

## 6. Decision

- [x] 6.1 Write `openspec/docs/adr/0001-map-style-rendering-path.md` per design D6: options table with every measurement, decision against the criteria of D5 in order, consequences for #542 (model and publishing job or client bundle), #543 (preview mechanism and latency promise), #544 (what an exported style carries), Mapbox account contents, appendix with the raw numbers and the device
- [x] 6.2 Review the ADR with the owner; set `Status: Accepted` — accepted 2026-11-06 (hybrid)
- [x] 6.3 ADR scenario test in `test_map_style_rendering.py`: file exists, status Accepted, exactly one path named, print mechanism named
- [x] 6.4 Update issues #542, #543, #544 with the consequences section; close #541 by the PR — comments posted on #542, #543, #544; #541 closes with PR #547

## 7. Clean-up and PR

- [x] 7.1 Delete every throw-away style from the Mapbox account; verify the list — *as done:* all 51 probe styles deleted and verified 404 through `…/draft`; the hand-built duplicates are not probes and wait for the owner (ADR, Mapbox account)
- [x] 7.2 Build the PR branch into `epic/map-styles` by cherry-picking the script, fixture, tests, `.env.ports.example` and ADR commits; `test_epic_branch_is_clean` scans `survey/` for `basemap_proto` and `maplibre` — *as done:* no cherry-pick needed; the prototype was committed only on `feat/map-styles-render-proto`, this branch never held it
- [x] 7.3 Open the PR against `epic/map-styles`; keep the prototype commits on `feat/map-styles-render-proto` for reference until the epic ships — PR #547
