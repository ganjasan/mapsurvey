## Why

Every Mapsurvey map sits on one of three real-world tile sets (`streets`, `satellite`, `topo`), so a
survey can only ask about places that exist on Earth's map. Two audiences want to ask about a
picture instead:

- **Worldbuilders and tabletop game masters** (r/worldbuilding, r/dndmaps, r/mapmaking) draw
  their own maps and have an audience in hand: players, readers. They are also the shareable
  story: a "participatory session by the Night City administration" or a Gondor survey is a
  Reddit post that demonstrates the whole product (drop a pin, draw a route, react to others' marks
  on the shared map, read the public results) with no explanation needed.
- **Creators with an indoor or private plan** (a shopping centre floor, a campus, a festival
  ground, a factory) are the paying version of the same need. This change serves them only
  partly, because the image is not placed on the real map. A georeferenced plan is a follow-up
  change.

This change adds the smallest thing that unlocks the first audience: an uploaded image used as the
map itself.

## What Changes

- A creator can upload **one image per survey** (PNG/JPEG/WebP) as an **image basemap**. When it is
  enabled, every map in the survey shows that image instead of the tile basemaps. Tiles and the
  image do not mix: a picture of Middle-earth over the streets of Bishkek means nothing.
- The image is **not georeferenced**. It is placed on a fixed, small rectangle around 0°, 0°
  (Null Island), sized to the image's aspect ratio. At that scale Mercator distortion is negligible,
  so geometry drawn on the picture keeps its shape. **Nothing downstream changes**: answers stay
  `PointField`/`LineStringField`/`PolygonField` in SRID 4326, and the shared map, reference layers,
  conditional visibility, public results, Responses and GeoJSON export all work as they are. The
  coordinates simply have no meaning outside this survey, and the export says so.
- On an image-basemap survey the map is **confined to the image**: the view cannot pan off it,
  zoom is limited to what the image resolution supports, and the start view defaults to the whole
  image rather than to a real-world position.
- Features that assume the real world are **switched off** on such a survey: the place-search box,
  "centre on my location" (`use_geolocation`), the basemap switcher, and the per-section
  `override_basemap`. The editor hides them rather than letting a creator set them to no effect.
- Every map surface renders the image through **one shared partial**, the same rule
  `basemap_layers.html` already follows for tiles. The surfaces are: the respondent map, the editor
  section map picker, the layer object editor, the Responses map pane and Overview thumbnail, the
  per-response map modal, and public results map blocks.
- The upload is **validated and normalised off the web worker**: a size cap, a pixel cap (to guard
  against decompression bombs), and re-encoding to WebP with a capped long side. The processed
  image lives on the public media tier under a random key, like other creator artwork.
- The image basemap **rides ZIP export/import and survey duplication**, so a fantasy survey can be
  shared as a template.
- Not breaking: existing surveys keep `basemaps`/`default_basemap` as they are. The image basemap
  is opt-in per survey.

## Capabilities

### New Capabilities
- `image-basemap`: uploading, validating and storing a survey's image basemap. How every map
  surface renders it in place of tiles, with bounds, zoom limits and the default view. Which
  real-world features are disabled while it is active. What the coordinates mean in exports.

### Modified Capabilities
- `survey-serialization`: the ZIP archive carries the image basemap and restores it on import.
  Archives without one import as before.
- `media-storage`: the image basemap joins "creator artwork is publicly readable" (public tier,
  random key).

Note: `basemap-providers` (introduced by the unarchived change `basemap-mapbox-outdoors`, already
merged in code) states "which provider backs each basemap slug". The image basemap is deliberately
**not** a fourth slug in that list, because it is a per-survey upload rather than a provider, so that
spec is not modified here. If `basemap-mapbox-outdoors` is archived first, re-check its wording
for any claim that every map shows a tile provider.

## Impact

- **Model**: new fields on `SurveyHeader` for the image and its pixel dimensions (exact shape in
  `design.md`), plus a migration. Draft copies and versions copy the file reference the way they
  copy `basemaps`, so a draft can change the image without touching the published survey
  (`design.md` D2).
- **Upload path**: new editor endpoint and a Celery task for decode/re-encode. Pillow must not
  decode an arbitrary upload inside a gunicorn worker. The 2026-09-15 memory incident showed a
  worker keeps its largest request's RSS for life, and an 8k × 8k RGBA image decodes to ~256 MB.
- **Templates**: `partials/basemap_layers.html` (or a sibling partial it delegates to),
  `base_survey_template.html`, `editor/partials/section_map_picker.html`,
  `editor/partials/survey_settings_panel.html`, `editor/layer_editor.html`,
  `editor/partials/analytics_geo_map.html`, `editor/partials/analytics_overview_pane.html`,
  `editor/partials/analytics_session_detail.html`, `public_results.html`. The last two tile
  hard-codings (`analytics_overview_pane.html`, the settings-panel previews) have to learn about
  the image too.
- **Serialization / cloning / versioning**: `survey/serialization.py`, `survey/cloning.py`,
  `survey/versioning.py`.
- **AI generation** (`survey/ai/materialize.py`) is untouched: it cannot produce an image, and a
  generated draft keeps tile basemaps.
- **Load**: the whole point is a Reddit post, and a successful one looks like the lecture-hall
  burst `loadtest/` models. The image is one static file from the media tier/CDN rather than a tile
  fan-out, so it is cheaper than tiles, but the shared-map GeoJSON endpoint is built per request.
  Run the k6 burst on a PR preview before the marketing push.
- **Legal/marketing (outside code)**: showcase surveys must use maps we have the right to show
  (fan artists with permission, public-domain worlds, or our own parody city), not official
  Night City / Middle-earth artwork. Tracked with the Reddit plan, not in this change.
- **Out of scope**: georeferencing (placing a plan on the real map), tiling very large images, more
  than one image per survey, per-section images.
