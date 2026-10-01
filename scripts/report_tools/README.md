# report_tools — building blocks for a survey report and materials kit (skill `survey-report`)

Generic pieces lifted from the three reports built on 2026-10-01 (Remington, Pszów, Whitehouse).
The survey-specific parts (question codes, place names, themes, the narrative) live next to the
report in the gitignored dossier, never here: this repo is public, and resident answers must not
reach it.

| File | What it does |
|---|---|
| `maplib.py` | JSON map spec → exact-size PNG with headless Chromium + Leaflet. Bases `osm`, `sat` (Mapbox satellite, token from `$MAPBOX_ACCESS_TOKEN` or the repo `.env`, used only to render; never shipped), `sat-muted`, `none`. Layers: `geojson` (with `styleBy` classes), `heat`, `lines`, `badges` (numbered circles), `labels`, `dots`, `scale`. `render(spec, out)` / `render_many(jobs)`. Scratch pages go to `./render/`. |
| `geo.py` | `haversine_m`, `nearest` (distance to the nearest feature of a layer), `hotspots` (grid cells + merge, ranked), `georeference` (fit a customer's map image to coordinates through features both show, e.g. the existing bins; returns a pixel→lat/lon function and residuals). |
| `pdf.py` | HTML → PDF: A4 pages with a footer for print, or `--single` one tall page exactly as on screen (what customers asked for). |

Run from the venv; Playwright's Chromium is already installed there. Charts are drawn per report
(matplotlib PNG, or inline SVG + CSV as in Pszów); see the skill for the palette and conventions.
