# ADR 0001: How a map style reaches the map

- **Status:** Accepted (product owner, 2026-11-06)
- **Date:** 2026-11-06
- **Deciders:** product owner
- **Change:** `map-styles-rendering-path` (#541), epic Map styles #545
- **Vision:** `openspec/docs/vision/map-styles.md` (DE-1, BR-1)

## Context

A workspace map style (epic #545) must show on every map surface and on the printed form. Today all eight map surfaces are Leaflet 1.4 over Mapbox **raster** tiles (`styles/v1/<style>/tiles/256/…@2x`), and the printed form fetches its frame from the Mapbox **Static Images** API by style id. Paper A and Paper B are hosted styles in the Mapsurvey account; `scripts/mapbox_style_publish.py` now rebuilds both from a settings document, layer for layer.

Three paths were on the table:

- **vector** — MapLibre GL renders the generated style JSON in the browser (Leaflet stays above it through `maplibre-gl-leaflet`); no per-style state in Mapbox.
- **hosted-raster** — every style is a hosted Mapbox style, served as raster tiles; Leaflet unchanged.
- **hybrid** — hosted raster everywhere respondents and readers look, vector only for the live preview in the style editor.

## Options and measurements

Copenhagen demo survey, section "spot", Paper A, view set to z15 over the city centre (55.6795, 12.5780). Desktop 1280×800; phone 390×844 at DPR 3 with 4× CPU throttling. Headless Chromium 1248, two runs each, dev stack on 2026-11-06. Full numbers in the appendix.

| | raster 256 (today) | raster 512 (#522) | vector (MapLibre) |
|---|---|---|---|
| Billable requests per screen, desktop | 24 tiles | 6 tiles | 12 tiles (+ 4 glyph, 2 sprite, 1 TileJSON) |
| Billable requests per screen, phone | 8 tiles | 2 tiles | 12 tiles (+ 4 glyph) |
| Price per 1 000 tiles (first paid tier) | $0.50 Static Tiles | $0.50 Static Tiles | $0.25 Vector Tiles |
| **Cost per 1 000 phone screens** | **$4.00** | **$1.00** | **$3.00** |
| Cost per 1 000 desktop screens | $12.00 | $3.00 | $3.00 |
| Bytes per screen, desktop / phone | 1.24 MB / 0.39 MB | 1.33 MB / 0.41 MB | 1.38 MB / 1.19 MB |
| Map JS on the respondent page (gzip) | Leaflet 40 KB | Leaflet 40 KB | Leaflet 40 KB **+ MapLibre 248 KB** |
| Last tile after setView, desktop | 0.46–0.60 s | 0.58–0.80 s | 1.04–1.37 s |
| Last tile after setView, phone (4× CPU) | 0.41–0.46 s | 0.36–0.38 s | **2.03–4.24 s** |
| Respondent flow (drag, crosshair point, pop-up, switcher, reference layers, objects, line) | works | works | works, identical results, no console errors |
| Leaflet ↔ GL position agreement | — | — | ≤ 1.14 CSS px at rest, after pan, z17 and flyTo |
| Editor preview after a change | needs a publish (below) | needs a publish | 0.8–2.1 s desktop, 2.6–3.3 s phone (software GL, see caveats) |
| Printed frame and reference image | Static Images by style id | same | **needs a hosted copy anyway** |

**Mapbox account and cache behaviour** (tasks 2.5–2.6):

- Styles per account: **unlimited** (Styles API docs); 50 styles created in 21 s without refusal.
- Styles API write limit: **50 requests per minute** — the 51st write in the minute (a delete) got `429`. Reads 2 000/min.
- Style `GET` and list responses are cached by CloudFront for **15 min** (+15 min stale-while-revalidate); query-string cache busters are ignored. `…/<id>/draft` is not served from cache and is the way to verify state.
- After **creating** a style: Static Images and raster tiles render it immediately (0.9 s).
- After **updating** a style in place (park colour → red): Static Images with `fresh=true` and the style JSON show the change in **0.8 s**; raster tiles (`Cache-Control: max-age=43200, s-maxage=7200`) and Static Images without `fresh` **did not change within 20 minutes**.
- Mapbox vector tiles and classic styles are allowed in MapLibre; tiles are billed per request instead of per map load; attribution "© Mapbox © OpenStreetMap" is required.

## Decision

**hybrid.**

1. **Respondent, creator and public surfaces, and print, use hosted raster at 512 px.** A workspace style is published by the generator to the Mapsurvey Mapbox account and shown as `tiles/512` with `tileSize: 512, zoomOffset: -1` (#522's shape). The printed frame and the mark-recognition reference image come from **Static Images** of the **same style id**, exactly as Paper A works today — no change to the print pipeline.
2. **Hosted styles are immutable.** Saving a style in the editor creates a **new** Mapbox style (a new id) and never `PATCH`es one that a survey can show; the `MapStyle` row keeps the id of each published version. This is forced by the cache: an in-place update leaves respondents on tiles up to 2 h old at the CDN and 12 h in the browser. A survey version pins the style version it was published with (vision FE-7), so the id a respondent sees never changes under them. Ids no survey version references are deleted by a periodic job.
3. **The style editor previews in the browser.** The editor page loads MapLibre and renders the generated style JSON directly, so a control change repaints without publishing; the "print" tab of the preview is a Static Images frame of the last saved version (`fresh=true`). MapLibre is **only** on the editor page — never on a respondent, Responses or public page.

### Against the criteria (design D5, in order)

1. **Print (gate).** Hosted raster prints by style id with no new code. Vector alone cannot print without a hosted copy, so a vector path is a hybrid in any case.
2. **Respondent behaviour (gate).** Both paths pass every flow tried. Vector on the phone took 2–4 s to the last tile against 0.4 s for raster, and adds 248 KB gzip of JS (six times Leaflet) to the page a phone loads on a bus. The phone gate (≤ +0.5 s) is not met by vector under the measured conditions.
3. **Cost.** Raster 512 is the cheapest per phone screen ($1.00 / 1 000), vector $3.00, today's raster 256 $4.00. Moving all Mapbox basemaps to 512 (#522) is a saving on its own.
4. **Editor loop.** Hosted-only would make each slider movement a publish (≥ 0.9 s, 50 writes a minute per account across all workspaces). The in-browser preview removes publishing from the loop; publishing happens on Save.
5. **Limits.** Unlimited styles; 50 writes a minute is the binding limit — one write per Save and one delete per sweep stay far below it. Saves are serialised through one Celery queue so a burst of creators cannot hit `429`.
6. **Code touched.** Respondent and creator surfaces: none beyond resolving a style id into the existing tile layer. Editor: one new page with MapLibre.

## Consequences

**#542 — style model, library, presets**
- `MapStyle` (workspace, name, settings JSON, base style version) and `MapStyleVersion` (style, settings snapshot, `mapbox_style_id`, created) — a version row per Save, immutable.
- The generator moves from `scripts/mapbox_style_publish.py` into `survey/` unchanged; publishing runs in a Celery task on its own queue (rate limit 50 writes/min), with `MAPBOX_STYLES_TOKEN` on the worker only.
- System presets (Streets, Topo, Paper A, Paper B) are library rows whose versions point at existing ids; Satellite stays Esri.
- Survey `basemaps` / `default_basemap` / `override_basemap` reference a style version; existing slugs map onto the presets. A published survey version stores the style version ids it shows.
- A sweep deletes Mapbox styles whose version no survey version references and that are older than a grace period (the CDN keeps tiles for up to 12 h).
- Switch every Mapbox layer to 512-px tiles in the same place (#522).

**#543 — editor**
- MapLibre GL (with `maplibre-gl-leaflet` to reuse the survey frame and layers) on the editor page only; preview latency to promise: about a second on desktop, a few seconds on a phone.
- The print preview is Static Images `fresh=true` of the last saved version; "unsaved changes" are labelled as not yet in print.
- Save = publish a new version (Celery), show progress, then switch surveys that follow "latest" on their next publish — never silently under a live survey.

**#544 — import/export**
- An exported style carries the settings document and the base style version — never a Mapbox id. Import creates a new style and publishes its first version.

**Mapbox account**
- Holds one style per published style version plus the presets. Delete the duplicate hand-built styles (two extra "Print A (block)", the "Print B (grey)" and "Print C (streets)" pairs) once nothing references them.

## Caveats

- Phone figures come from headless Chromium with DPR 3 and 4× CPU throttling, not from a real device; headless WebGL is software-rendered (SwiftShader), which inflates every vector timing. The decision does not depend on the vector phone number: vector stays off respondent pages for the JS weight and the print gate alone.
- Byte counts are response bodies as received (compressed where the server compressed).
- Freshness was measured once, on one style and one tile; the 20-minute bound is a lower bound for the stale window.

## Appendix: raw numbers

`render_s` = seconds from `map.setView` to the last Mapbox response with 2 s of quiet after it.

| path | viewport | run | render_s | requests by kind | bytes |
|---|---|---|---|---|---|
| raster256 | desktop | 1 | 0.46 | raster_tile 24 | 1 242 073 |
| raster256 | desktop | 2 | 0.60 | raster_tile 24 | 1 242 073 |
| raster256 | phone | 1 | 0.41 | raster_tile 8 | 386 539 |
| raster256 | phone | 2 | 0.46 | raster_tile 8 | 386 539 |
| raster512 | desktop | 1 | 0.80 | raster_tile 6 | 1 332 409 |
| raster512 | desktop | 2 | 0.58 | raster_tile 6 | 1 332 409 |
| raster512 | phone | 1 | 0.36 | raster_tile 2 | 406 228 |
| raster512 | phone | 2 | 0.38 | raster_tile 2 | 406 228 |
| vector | desktop | 1 | 1.37 | vector_tile 12, glyphs 4, sprite 2, tilejson 1 | 1 384 784 |
| vector | desktop | 2 | 1.04 | vector_tile 12, glyphs 4, sprite 2, tilejson 1 | 1 384 784 |
| vector | phone | 1 | 4.24 | vector_tile 12, glyphs 4 | 1 185 681 |
| vector | phone | 2 | 2.03 | vector_tile 12, glyphs 4 | 1 185 681 |

Leaflet ↔ GL page-space distance (CSS px) for four landmarks — desktop: at rest 0.71/0.64/0.59/0, after pan 0.33/0.61/0.32/0.39, z17 0.13/0.48/0.14/0.55, after flyTo 0.16/0.46/0.78/0.70; phone: at rest 1.08/1.14/0.74/0.50, after pan 0.78/1.05/0.36/0.49, z17 0.50/0.62/0.62/0.94, after flyTo 0.65/0.27/0.28/0.26.

Editor repaint (MapLibre `idle`): one colour on two layers 1 354 ms desktop / 2 612 ms phone; `setStyle` diff Paper A → Paper B 2 115 / 3 271 ms; back to A 824 / 3 185 ms.

Freshness probe: create 0.87 s; after create, Static Images (fresh and cached) and a raster tile rendered the new style on first request; after `PATCH`, Static Images `fresh=true` and style JSON 0.8 s, raster tile and Static Images without `fresh` unchanged at 20 min (tile `Cache-Control: max-age=43200, s-maxage=7200`).

Account probe: 50 tiny styles created in 21.3 s, no refusal, no rate-limit headers on responses; deletes 51–100 in the same minute got `429`; all 50 deleted with backoff and verified gone through `…/draft` (404). The account's list was unchanged throughout because list responses are CDN-cached for 15 min.

Prototype: branch `feat/map-styles-render-proto` (commit f1578f70), dev-only `?basemap_proto=vector|raster512`, MapLibre GL 5.6.0, maplibre-gl-leaflet 0.1.3. Pricing from mapbox.com/pricing on 2026-11-06.
