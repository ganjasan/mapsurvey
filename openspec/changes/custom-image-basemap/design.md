## Context

Basemaps today are three tile slugs stored per `SurveyHeader` (`basemaps`, `default_basemap`) with a
per-section `override_basemap` and a per-block `PublicResultsBlock.basemap`. Tiles are drawn by
`partials/basemap_layers.html`, which five surfaces include (respondent map, section map picker,
layer object editor, Responses map pane, per-response map modal). Three more build a tile layer by
hand: the Responses Overview thumbnail (`analytics_overview_pane.html`), the settings panel's
previews (`survey_settings_panel.html`) and public results (`public_results.html`).

Every map uses Leaflet's default `EPSG:3857` CRS, and every answer geometry is PostGIS in SRID 4326.
The respondent map also offers place search (`MapPlaceSearch`, Mapbox geocoding) and optional
auto-centring on the device position (`use_geolocation`).

Header-level map settings are copied, not borrowed: `clone_survey_for_draft()` copies
`basemaps`/`default_basemap` into the draft, and `publish_draft()` copies them back. Reference
layers are the exception: they are borrowed from the canonical survey through `layer_owner()`.
`purge_survey()` deletes the whole family (canonical, versions, draft) at once and deletes each
header's `cover_image` through the storage API.

Constraints from production:
- A gunicorn worker keeps the RSS of its largest request for life (2026-09-15 incident). Decoding
  an image in a web worker is exactly that kind of request: an 8192 × 8192 RGBA image is 256 MB
  decoded.
- A merge reaches production within minutes, and the owner prefers no kill switches. The feature
  is opt-in per survey, so a survey that never uploads an image behaves exactly as today.

## Goals / Non-Goals

**Goals:**
- A creator uploads one image and every map in the survey shows it instead of tiles.
- No change to how answers are stored, aggregated, moderated, exported or imported, apart from
  carrying the image itself.
- One renderer for the image, used by every map surface, the same way `basemap_layers.html` is
  the one place tiles come from.
- The upload cannot hurt a web worker's memory, and an unvalidated file is never publicly readable.

**Non-Goals:**
- Georeferencing (placing a plan on the real map by control points). Follow-up change.
- Tiling large images (a Zoomify/DeepZoom pyramid). The long-side cap makes one file sufficient
  for v1.
- More than one image per survey, per-section images, mixing tiles with an image.
- Meaningful metric distances or areas on an image map. Anything that already computes metres
  keeps doing so on fake coordinates, and the numbers are relative only.

## Decisions

### D1. Place the image on Null Island in the default CRS, not `L.CRS.Simple`

The image occupies a fixed rectangle centred on 0°, 0°. Its longer side spans `IMAGE_SPAN_DEG = 1.0`
degree and the shorter side follows the aspect ratio. Bounds are
`[[-h/2, -w/2], [h/2, w/2]]` in degrees, where `w`/`h` is the span of each side. They are computed
in one Python helper (`survey/image_basemap.py::bounds_for(width, height)`) and passed to the browser
as data. JavaScript never recomputes them.

- At ±0.5° latitude the Mercator scale factor differs from 1 by less than 0.004 %, so shapes drawn
  on the picture are not visibly distorted.
- Geometry stays valid SRID 4326. Draw tools, `fitBounds`, the shared map, `LayerManager`,
  heat maps, the object editor, reference layers and every GeoJSON consumer work unchanged.
- *Alternative: `L.CRS.Simple` with pixel coordinates.* It is cleaner semantically, but every map
  constructor, every stored geometry and every server-side spatial query would need a second
  coordinate path. It is also incompatible with tile surfaces sharing code. Rejected.
- *Alternative: let the creator place the image anywhere on Earth.* That is georeferencing
  (non-goal). It would also put fantasy pins on real streets in exports.

Because the rectangle is fixed, **replacing the image with one of the same aspect ratio keeps
existing answers in place**. A different aspect ratio shifts them. See D6.

### D2. Storage: fields on `SurveyHeader`, copied like `basemaps`

New fields on `SurveyHeader`:

| field | type | meaning |
|---|---|---|
| `basemap_mode` | `CharField` `tiles`/`image`, default `tiles` | which kind of basemap the survey shows |
| `image_basemap` | `ImageField` (public tier, `upload_to` → `basemap_images/<uuid4>.webp`) | the processed image |
| `image_basemap_width`, `image_basemap_height` | `PositiveIntegerField` null | pixel size of the processed image |
| `image_basemap_state` | `CharField` `''`/`processing`/`failed` | upload pipeline state for the editor |
| `image_basemap_error` | `CharField(255)` blank | the reason shown when `failed` |

The image is **active** only when `basemap_mode == 'image'` and `image_basemap` is set. One
predicate, `SurveyHeader.uses_image_basemap`, is the only place that rule is written.
Keeping the image while switching back to `tiles` lets a creator compare without re-uploading.

Ownership follows `basemaps`, not layers: `clone_survey_for_draft()` and `publish_draft()` copy all
five fields, so the file **name** is shared, not the bytes. A draft can therefore replace the image
without touching the published survey until publish.

- *Alternative: borrow from the canonical survey like layers do.* That means one copy and no
  sharing bookkeeping. But replacing the image would move every live respondent's map mid-collection
  with no draft/publish step. Layers accept that because they are content objects with their own
  editor banner. A basemap is survey configuration and belongs with the draft workflow. Rejected.
- *Alternative: a separate `SurveyBasemapImage` model.* That is justified only for several images or
  a job history. It is one image per header here. Rejected for v1.

**Deleting a shared file**: when an image is replaced or cleared, the old file is deleted only if
no other `SurveyHeader` still names it (`image_basemap=<name>` count query). `purge_survey()` deletes
it once per distinct name across the family. Local and S3 deletes are already idempotent, so a
duplicate delete is harmless, but the distinct set keeps the logic readable.

### D3. Upload pipeline: web stores the raw file privately, Celery decodes

1. `POST /editor/surveys/<uuid>/basemap-image/` (editor role, same gate as survey settings). It
   checks the content type and size (`IMAGE_BASEMAP_MAX_UPLOAD_BYTES`, 20 MB) **without decoding**.
   It streams the upload to the **private** tier under `basemap_uploads/<uuid4>`, sets
   `image_basemap_state='processing'`, enqueues `process_image_basemap(survey_id, raw_key)` and
   returns the settings card partial.
2. The Celery task opens the raw file with Pillow. It sets
   `Image.MAX_IMAGE_PIXELS = IMAGE_BASEMAP_MAX_PIXELS` (64 MP) so a decompression bomb raises
   before allocating, and checks `verify()` first. It applies EXIF orientation, converts to RGB(A)
   and downsizes so the long side is ≤ `IMAGE_BASEMAP_MAX_SIDE` (8192 px). It encodes WebP (quality
   85), saves to the public tier, writes the dimensions and clears the state. Then it deletes the
   raw file. On any failure it records `failed` + a translated reason and deletes the raw file.
3. The settings card polls every 2 s while `processing` (the same pattern as import job cards) and
   swaps in the preview when done.

The task is idempotent per `raw_key`. A redelivered message whose raw file is gone returns
without changes. A newer upload that finds a previous `processing` state supersedes it: the task
checks that the header still points at its `raw_key`, stored in a sixth field
`image_basemap_pending` (`CharField`, blank), before writing.

- *Why private for the raw file*: an unvalidated upload must never be readable at a public URL.
  The media-storage spec already separates tiers by readability.
- *Why WebP*: at 8192 px a PNG fantasy map is typically 20–60 MB, while WebP q85 is 2–6 MB. Every
  target browser decodes it.
- *Alternative: decode in the view with a small cap.* It is simpler, but it repeats the exact
  failure mode of the 2026-09-15 incident. Rejected.

### D4. One renderer: `ImageBasemap` + one config filter

- `survey/assets/js/image_basemap.js` defines `window.ImageBasemap.apply(map, cfg)`. It adds
  `L.imageOverlay(cfg.url, cfg.bounds)`, sets `maxBounds` (bounds padded by 10 %,
  `maxBoundsViscosity: 1`), computes `minZoom` from `map.getBoundsZoom(bounds)` − 1 and `maxZoom`
  from the native zoom where one image pixel is one screen pixel (+1 for pinch). It sets the map
  background to a neutral colour instead of the tile grey, and returns the bounds so the caller can
  `fitBounds` when it has no start view of its own.
- The config (`image_basemap.config_for(survey)`: url, bounds, width, height, or `null`) reaches
  each map as `JSON.parse('{{ survey|image_basemap_json|escapejs }}')`, written inline where the map
  is built. *Changed during implementation:* the first plan was a `json_script` partial, but every
  includer of `basemap_layers.html` includes it inside a `<script>` body, where a `json_script` tag
  cannot go. One filter used everywhere is also what the guard test below looks for.
- `partials/basemap_layers.html` branches at the top: on an image survey it calls
  `ImageBasemap.apply` and adds **no** tile layers and **no** base entries to the layers control. The
  control is still created when reference overlays need it. The five including surfaces therefore
  get the image with no change of their own.
- The three hand-built surfaces (Overview thumbnail, settings-panel previews, public results
  blocks) call `ImageBasemap.apply` instead of `L.tileLayer` when the config is present. Public
  results ignore `PublicResultsBlock.basemap` on an image survey.
- A template-guard test asserts that no template calls `L.tileLayer(` without also handling the
  image config. This is the lesson from the `basemap-mapbox-outdoors` second pass, where the
  Overview thumbnail was missed because it did not use the shared partial.

### D5. Real-world features off, in one place

`uses_image_basemap` drives all of them:
- **Respondent**: no `MapPlaceSearch` control, `use_geolocation` is not honoured, and
  `override_basemap` is ignored.
- **Start view**: a section or survey `start_map_postion` that lies **inside** the image bounds is
  honoured, which is how a creator frames the "Downtown" section with the existing map picker. One
  outside, including every real-world position left from before the switch, falls back to fitting the
  whole image.
- **Editor**: the settings card replaces the basemap checkboxes/default select with the image
  block when mode is `image`, and hides "use geolocation". The section map picker hides the basemap
  override and the search box. Values stay stored and come back if the creator switches to `tiles`.
- **AI generation and templates**: untouched. They always produce `tiles`.

### D6. Replacing an image on a survey with answers

If the survey family already has answers and the new image's aspect ratio differs from the old one
by more than 1 %, the settings card shows a confirm step. It says that existing marks will not line
up with the new picture. Same aspect ratio means no prompt (D1 keeps answers aligned). The check
runs in the view before enqueueing, from the old dimensions and the new file's header. Reading the
header with Pillow's lazy `open()` does not decode pixels.

### D7. Export and import

- **Survey ZIP** (`survey.json`): the header gains
  `"image_basemap": {"file": "basemap/<name>.webp", "width": W, "height": H}` and `"basemap_mode"`.
  The file sits under `basemap/`. On import the file is run through the **same** processing function
  as D3 (the import already runs on the Celery worker), because a ZIP is untrusted. A missing or
  invalid file leaves `basemap_mode='tiles'` and adds a report line, following the "missing structure
  image" warning pattern. Old archives without the key import as before.
- **Data download** (`download_data`): each GeoJSON FeatureCollection gets a foreign member
  `"mapsurvey_image_basemap": {"image": "basemap.webp", "bounds": [...], "note": "..."}`. The
  image itself is added to the ZIP, so someone opening the data in QGIS can load the picture as a
  raster with those bounds and see the marks where respondents put them.
- **Duplication**: there is no whole-survey copy in the product (only question/section
  duplication, which never touches the header), so nothing to do. ZIP export → import is the way to
  copy a survey and carries the picture. The archived version created by `publish_draft()` does
  copy the fields: the sessions moving there were drawn on the old picture.
- **Copying rule**: `image_basemap.copy_fields()` passes the file NAME,
  never the source's `FieldFile`. Django's file descriptor re-points a foreign `FieldFile` at the
  instance it is assigned to, so two rows would share one object and a replacement in one would rename
  the other in memory. A test caught exactly that.

### D8. Preview worker shares the web service's media namespace (found on PR #200)

On a PR preview, `namespace_from_env` named the prefix after `RENDER_SERVICE_NAME`. The web service
is `mapsurvey PR #200`, but its worker is `mapsurvey-celery PR #200`, so the two used different
prefixes. The task received the upload, found no raw file under its own prefix and returned in
0.14 s, which left the card on "Processing" forever. The same split breaks the Celery-side ZIP import
on every preview since #187. Production is unaffected: both services resolve the empty namespace.

Fix: the worker carries `MEDIA_NAMESPACE_SERVICE=mapsurvey` in `render.yaml`. On a preview,
`namespace_from_env` swaps the service part of the name for it and keeps the ` PR #N` / `-pr-N`
suffix, so both services write `previews/mapsurvey PR #200/`. That is exactly the web preview's
name, which `reclaim_preview_media` checks against Render's service list. Outside previews the
variable changes nothing.

- *Alternative: pin `MEDIA_S3_NAMESPACE` per preview.* The Blueprint cannot express a preview's
  name before Render creates it, which is why the namespace was derived in the first place.
  Rejected.

## Risks / Trade-offs

- [Coordinates look real and are not: an image survey's export puts points near 0°, 0° in the
  Gulf of Guinea] → The foreign member and its `note` in every GeoJSON, plus the image and bounds in
  the ZIP. The Responses map shows the image, never tiles.
- [An 8192-px WebP is heavy on a phone: ~4 MB download, ~256 MB decoded texture] → The long-side
  cap is a setting. Measure on a mid-range Android and an iPhone before the Reddit push. Tiling is
  the escape hatch if 8192 is too much.
- [A Reddit hug hits production (1 CPU / 2 GB)] → The image is one immutable CDN object with
  long cache headers, so it is not the bottleneck. The shared-map GeoJSON is. Run
  `loadtest/lecture-burst.js` on a PR preview with an image survey and a shared-map question.
- [Draft and published headers share a file name, so a careless delete breaks the other] → All
  deletes go through one helper with the "still referenced?" query (D2), and a test covers
  replace-in-draft-then-publish.
- [A creator switches an existing tile survey with real-world answers to `image`] → Old answers
  sit at real coordinates far outside the image bounds and simply do not show on the map. The
  settings card warns before switching when the family has geo answers.
- [Copyrighted artwork uploaded by creators] → It is ordinary user content under the existing terms
  and DMCA handling. Our own showcase uses maps we have rights to (proposal, Impact).

## Migration Plan

1. One additive migration: six nullable/defaulted fields on `SurveyHeader`, with `basemap_mode`
   defaulting to `tiles`. No data migration. Safe under the pre-deploy migrate, because the old
   instance never reads the new columns.
2. The deploy itself changes nothing for existing surveys (`tiles` everywhere).
3. Rollback: revert the code. The extra columns are harmless to the old code. Any survey switched
   to `image` renders tiles again on the old code, at its old start positions.
4. Bucket: `basemap_images/` sits under the existing public prefix and `basemap_uploads/` under the
   private one. No policy change is needed. Verify on the PR preview.

## Open Questions

- `IMAGE_BASEMAP_MAX_SIDE`: 8192 is the starting value. Confirm on real phones (see Risks). Lower
  it to 6144 if an iPhone stalls.
- Should the Reddit showcase surveys be marked `public` on the landing page list, or stay
  `unlisted` and be linked only from the posts? This is a marketing decision and is not blocking.
