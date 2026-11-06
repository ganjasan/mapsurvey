## Context

Every map in Mapsurvey is Leaflet 1.4.0 with raster tiles from `MAPBOX_URL` / `MAPBOX_OUTDOORS_URL` / `MAPBOX_PAPER_URL` / `MAPBOX_PAPER_B_URL` (Mapbox Static Tiles API, `tiles/256/…@2x`) and Esri for satellite. `partials/basemap_layers.html` builds the layers for the respondent page; seven other surfaces build their own from the same settings (create wizard, settings map picker and style preview, Responses overview and map modal, layer editor, public results). On top of Leaflet sit leaflet.draw 1.0.4, the crosshair placement flow, `L.SprayLayer`, `L.SprayAgreementLayer`, leaflet.heat, `RefLayerFactory` for reference layers and the layer switcher. Print (`survey/print/static_map.py`) fetches the frame from the Static Images API by style id and the same frame is the mark-recognition reference image.

Paper A and Paper B exist as styles in the owner's Mapbox account, built on 2026-11-06 by a script over `streets-v12` and referenced by id in settings. The vision wants a style to be a workspace object with up to 6–8 guided controls, previewed in the editor and used on every surface. Three paths are on the table:

- **A. Vector on the client.** MapLibre GL renders the generated style JSON; Leaflet stays for everything above the base map through `maplibre-gl-leaflet` (`L.maplibreGL`). No per-style state in Mapbox. Tiles come from the Mapbox Vector Tiles API (`mapbox.mapbox-streets-v8`) or another provider with an account.
- **B. Hosted raster.** Each style is created in the Mapsurvey account through the Styles API and served as raster tiles, exactly like Paper A today. Leaflet code untouched.
- **C. Hybrid.** B for respondent and creator surfaces; A only for the live preview in the style editor, where an upload round-trip would make every slider wait.

Constraints: one developer; `basemap-providers` forbids volunteer tile hosts; Mapbox cost must not grow faster than Pro revenue; the respondent page runs on mid-range phones and inside embeds; Safari/iOS keep no third-party cookies but that does not touch tiles.

## Goals / Non-Goals

**Goals**
- Decide A, B or C with numbers from one survey, one viewport, one style, and write the decision down as an ADR that #542–#544 build on.
- Produce the style publishing script that any path needs for print and that B needs for everything.
- Learn the Mapbox limits that bound the library's size and the editor's save loop.

**Non-Goals**
- Shipping any rendering change to a production surface.
- Choosing the set of guided controls (that is #543); the script takes a settings document but only the controls Paper A and B already use.
- Replacing Mapbox as the provider. If A needs a different vector source for licensing reasons, that is recorded as a finding, not pursued here.
- Styling satellite, reference layers or survey marks.

## Decisions

### D1. Measure on the respondent page only
The respondent map carries every Leaflet extension (draw, crosshair, spray, reference layers, switcher, popups) and the mid-range-phone constraint. If A works there it works on the creator surfaces; if it breaks there the other surfaces do not matter. Alternative: prototype all eight surfaces — rejected, eight times the work for no extra information.

### D2. Prototype behind a dev-only query parameter
`?basemap_proto=vector|raster` on the section page, honoured only when `DEBUG` is true, chooses the path for that page load. No setting, no kill switch, nothing persists (feedback: no kill switches; flag-masked is not fixed). The prototype commits live on this branch; the PR into `epic/map-styles` cherry-picks only the script, the ADR and tests, so the prototype never reaches the epic branch or production.

### D3. Paper A is the test style on the Copenhagen demo survey
Paper A exists in both forms already (a hosted style id for B, an exportable style JSON for A) and is the style the paper pipeline was tuned on. The Copenhagen demo survey (`seed_demo_survey`) has reference layers, geo questions of every type and a public results page, and is seeded on any dev stack. Measurements are taken at 1280×800 and on a phone viewport (390×844), z15 over the city centre, two runs each, CDN miss and hit separated — the protocol #522 already used, so raster numbers are comparable.

### D4. The publishing script is a real deliverable, not scaffolding
`scripts/mapbox_style_publish.py` reads a settings document (`base`, `poi`, `buildings`, `labels`, `place_names`, `park_color`, `water_color`, `road_contrast`, `greyscale` — the knobs Paper A/B used), fetches the base style once (`styles/v1/mapbox/streets-v12` with the server token), applies the settings as layer edits, and `POST`s or `PATCH`es `styles/v1/<account>` with a deterministic `name` so a re-run updates instead of duplicating. It prints the style id and the Static Images URL of a check frame. Pure functions (`apply_settings(style, settings) -> style`) are unit-tested on a stored copy of the base style; network calls are behind one `MapboxStylesClient` the tests stub. #542 moves the generator into `survey/` unchanged.

*As built:* reproducing Paper A and Paper B exactly took 17 keys, not the 8 above — five removals (`poi`, `paths`, `shields`, `relief`, `regions`), four colours (`land`, `park`, `water`, `boundary`), `buildings`, `roads`, `labels`, `place_names_maxzoom`, `greyscale`, plus `name` and `base`. Both settings files reproduce the hosted styles layer for layer (81 layers, 0 differences, fixtures of 2026-11-06). The editor's 6–8 controls (#543) map onto these keys; the keys are the storage format, not the UI. The token is the existing secret `MAPBOX_STYLES_TOKEN` (styles:list confirmed), not `MAPBOX_SERVER_TOKEN`, which serves Static Images to the print pipeline. The account holds duplicate names from the hand-built runs (three "Print A (block)", two each of "Print B" and "Print C"); the script refuses an ambiguous name rather than guess, and the duplicates go in task 7.1.

### D5. Decision criteria, in order
1. **Print**: can the path produce the printed frame and the reference image from the same style the respondent saw? A path that cannot is out.
2. **Respondent behaviour**: draw, crosshair, spray, reference layers, switcher, popups unchanged on desktop and phone; no regression in first render beyond +0.5 s on the phone viewport.
3. **Cost at 1 000 respondent sessions**: billable requests (Static Tiles vs Vector Tiles API) and bytes.
4. **Editor loop**: time from "slider moved" to "preview updated".
5. **Limits**: styles per account, Styles API rate limits, CDN propagation after a style update, Static Images on a style updated a minute ago.
6. **Code touched** and new dependencies (MapLibre GL is ~250 KB gzipped; the respondent page currently ships Leaflet at ~40 KB).

Criterion 1 is a gate, 2 is a gate, 3–6 are weighed in the ADR.

### D6. ADR format
`openspec/docs/adr/0001-map-style-rendering-path.md`: Status, Context, Options with the measurement table, Decision, Consequences (what #542–#544 must do, what the Mapbox account must hold, what the editor can promise about preview latency), and the raw numbers in an appendix. The ADR is the artifact #542's design reads first.

## Risks / Trade-offs

- [Mapbox vector tiles may be licensed only for Mapbox GL JS, not MapLibre] → Read the current Vector Tiles API terms before building A; if MapLibre is not allowed, A is measured with Mapbox GL JS v3 (proprietary, per-load billing) and the ADR records the licence as a cost line. A third-party vector source is a finding, not a prototype.
- [Styles API has an undocumented ceiling on styles per account] → Create 50 throw-away styles in a loop, record where it refuses, delete them all; the number bounds the library and goes into the ADR.
- [CDN keeps an old raster for a while after a style update] → Measure propagation (update colour, poll a tile until it changes); if minutes, the editor preview under B must come from Static Images with `fresh=true`, not from tiles — that is option C's reason to exist.
- [#522 lands mid-investigation and moves the raster baseline] → Measure raster at both 256 and 512 from the start; the cost line in the ADR shows both.
- [The prototype leaks into the epic PR] → The PR is built by cherry-pick of the script/ADR/test commits; `test_no_prototype_parameter` fails if `basemap_proto` appears anywhere under `survey/`.
- [Measuring on a laptop misrepresents phones] → Phone numbers come from a real Android device on Wi-Fi through Chrome remote debugging, not from DevTools throttling alone; the device and OS are named in the appendix.

## Migration Plan

Nothing to deploy. Order of work on the branch: script with tests → B prototype (uses the script) → A prototype → measurements → ADR → cherry-pick PR into `epic/map-styles`. The throw-away Mapbox styles are deleted in the same session they are created; the account keeps only Paper A, Paper B and a `print-check` style the script's documentation points at. Rollback: delete the branch.

## Open Questions

- Does Mapbox's current ToS allow its vector tiles in MapLibre? (Resolved in task 3.1, before any A code.)
- Is there a styles-per-account limit, and does it differ between the free and the paid Mapbox plan the account is on? (Task 2.5.)
- Can the Static Images API read a style the moment it is created, or is there a delay? (Task 2.6; decides whether the print pipeline can use a just-saved style.)
- Does `maplibre-gl-leaflet` keep Leaflet's coordinate space exact enough for the crosshair placement and the paper fiducials' assumptions, or does the GL canvas introduce sub-pixel drift? (Task 3.4.)
