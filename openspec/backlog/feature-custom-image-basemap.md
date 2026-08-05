# Custom image basemap (non-geographic maps via CRS.Simple)

**Type**: feature
**Priority**: medium
**Area**: frontend
**Created**: 2026-06-30

## Description

Let survey creators use a **custom image as the map background** instead of real-world
geography, so respondents can place points, draw lines, and draw polygons on a
non-geographic map. Origin story: a creator wants a map of the Satisfactory game world
to mark resource nodes and draw logistics routes — but the same capability unlocks a
whole class of maps that have coordinates without latitude/longitude.

Today the platform is hard-wired to real geography: every Leaflet map uses the implicit
Web Mercator CRS (`EPSG3857`) with OSM/Mapbox/Esri tile providers, and all geometry is
stored in PostGIS as `SRID 4326`. This feature introduces an alternative **image map
mode** built on Leaflet's `L.CRS.Simple` + `L.imageOverlay`, where the coordinate space
is the image's own pixel/world units rather than the globe.

## Use cases

- **Game / virtual worlds** — Satisfactory, Minecraft, fantasy game maps (resource nodes, routes, base layouts).
- **Indoor & venue maps** — floor plans, event/expo venues, campus maps ("mark where you'd put X").
- **Fictional / fantasy maps** — worldbuilding, tabletop, fan communities.
- **Historical & scanned maps** — annotate a scanned historic map or hand-drawn map.
- **Education** — ties directly to [digital contour maps](idea-digital-contour-maps-education.md):
  draw regions on *any* supplied image, not just real terrain (e.g. a blank/contour map handout).

## Scope (high level — details belong in the OpenSpec change)

- A **map mode** toggle on the survey (and/or section): `geographic` (current default) vs `image`.
- Upload/host a background image; capture its dimensions/bounds; configure initial
  center + zoom in image coordinates.
- Render the image map via `L.CRS.Simple` + `L.imageOverlay` across **all four** map
  surfaces, not just the respondent form: respondent flow, editor preview/picker,
  analytics geo map, and the public results page.
- Reuse the existing point/line/polygon draw widgets (they are CRS-agnostic — they emit
  GeoJSON coordinates as-is).
- Export/import must round-trip image-mode geometry without pretending it is WGS84.

## Key open question — geometry storage (decide in design)

This is the central architectural decision and the main reason this is a *change*, not a
quick edit. `Answer.point/line/polygon` are PostGIS `SRID 4326` fields; 4326 validation
constrains coordinates to lat ∈ [-90, 90], lng ∈ [-180, 180]. `CRS.Simple` produces
arbitrary pixel/world coordinates (e.g. 0..8192) that are **not valid** 4326 geometry.
Candidate approaches to weigh:

- Store image-mode geometry as **generic geometry (`SRID 0`)** or a separate set of fields.
- Store as **JSON** outside the GIS pipeline for image mode.
- **Normalize** image coordinates into a synthetic lat/lng box (hacky; breaks export semantics).

The export path also stamps a WGS84 CRS header (`urn:ogc:def:crs:OGC:1.3:CRS84`), which is
wrong for non-geographic geometry and needs a branch.

## Touch points (from a 2026-06-30 code recon — for the future OpenSpec change)

- `survey/templates/base_survey_template.html` — main respondent map (`L.map(...).setView`, geolocation, draw/serialize). Needs a `crs: L.CRS.Simple` branch; geolocation is N/A in image mode.
- `survey/templates/partials/basemap_layers.html` — replace/augment `L.tileLayer` with `L.imageOverlay(url, bounds)` for image mode.
- `survey/models.py` — `SurveyHeader`/`SurveySection`: new fields (map mode, image URL/file, dimensions/bounds, center/zoom in image units). `Answer.point/line/polygon` storage (the open question above).
- `survey/views.py` — geometry write (`GEOSGeometry` → 4326), map context builder, and `download_data` export CRS header all need image-mode branches.
- `survey/forms.py` — draw widgets are largely CRS-agnostic; little change expected.
- Other map surfaces hardcode the geographic basemap and must be made CRS-aware: `editor/survey_create.html`, `editor/survey_settings.html`, `editor/partials/section_map_picker.html`, `editor/partials/analytics_geo_map.html`, `editor/partials/analytics_session_detail.html`, `public_results.html`.

## Notes

- Related basemap-configurability items: [WMS/WFS basemap support](feature-wms-wfs-basemap.md) (real-geo overlays) and the done [satellite/topo basemaps](feature-satellite-basemap.md). This one is different in kind: it leaves geographic CRS entirely.
- Also adjacent to [map tagging with categorized pins](feature-map-tagging-pins.md) — categorized pins on an image map is a natural combo for game/indoor use cases.
- The page config and ZIP export/import paths must be reviewed so image-mode surveys round-trip cleanly.
- Suggested next step: promote to an OpenSpec change (`/opsx:new`) and resolve the geometry-storage question in `design.md` before writing code (project rule: no code without an active change).
