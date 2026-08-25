# Design: reference-overlay-layers

## Context

Respondent map is one persistent Leaflet instance (`base_survey_template.html:172`)
living outside the HTMX-swapped `#section-panel`; per-section state is re-applied by
`initSection()` (`base_survey_template.html:931`). Basemaps show the extension point:
survey-level JSON config + per-section override + `L.control.layers(_baseMaps, null)`
whose overlay slot is empty (`basemap_layers.html:26`). Mockups: `user-journey.mockup.html`.

## Goals / Non-Goals

**Goals**: vector GeoJSON overlays, creator-configurable, respondent-visible,
per-section visibility, ZIP round-trip, FD-14-ready feature identity.

**Non-Goals**: raster overlays (#147), drawing in editor (#148), answer-driven zoom /
enforcement (FD-14), server-side geometry simplification, per-volunteer assignment (FD-2).

## Decisions

### D1. Storage: GeoJSON text in the database, not a FileField

`SurveyMapLayer.geojson` is a `TextField` holding the (re-serialized) GeoJSON.

- The S3 media bucket is `public-read` with no per-object ACL story
  (`storage_backends.py`) — a FileField would make every uploaded layer world-readable
  regardless of survey visibility. DB storage closes that hole outright.
- ≤10 MB per layer is comfortably inside Postgres TEXT territory; the row is read by
  one endpoint that caches.
- ZIP round-trip and deletion become trivial (no orphaned media, no `.path`-on-S3 trap
  that `collect_structure_images()` has).

Rejected: FileField + private bucket (no private-media infrastructure exists; building
it is a bigger change than the feature).

### D2. Model shape

```python
class SurveyMapLayer(models.Model):
    survey = models.ForeignKey(SurveyHeader, on_delete=models.CASCADE, related_name='map_layers')
    name = models.CharField(max_length=100)
    color = models.CharField(max_length=7, default='#2c7be5')   # RRGGBB, validated
    label_field = models.CharField(max_length=100, blank=True, default='')
    key_field = models.CharField(max_length=100, blank=True, default='')
    show_popups = models.BooleanField(default=False)
    geojson = models.TextField()
    feature_count = models.PositiveIntegerField(default=0)
    size_bytes = models.PositiveIntegerField(default=0)
    position = models.PositiveIntegerField(default=0)           # render order
    updated_at = models.DateTimeField(auto_now=True)
```

`SurveySection.hidden_layers = JSONField(default=list)` — list of layer IDs hidden on
that section. Default-visible semantics: a new layer shows everywhere without touching
sections; deleting a layer leaves harmless stale IDs (filtered on read). IDs are
remapped on ZIP import (section deltas reference export-order indexes, see D6).

`key_field` is stored and round-tripped but has no UI consumer yet — it is the FD-14
contract (feature property whose values will map to choice codes).

### D3. Upload validation (server, one helper)

`survey/layers.py: validate_layer_upload(file) -> (geojson_str, feature_count, properties)`:

- size ≤ `MAX_LAYER_BYTES` (10 MB) before reading fully; reject non-UTF-8.
- `json.loads` → must be FeatureCollection / Feature / bare geometry (normalized to a
  FeatureCollection).
- every coordinate within WGS84 ranges (lng ∈ [-180,180], lat ∈ [-90,90]) — the
  honest "is this actually 4326" check; reject otherwise with a message naming the
  likely cause (projected CRS).
- feature count ≤ 5000.
- The stored value is `json.dumps` of the parsed object — never the raw upload bytes
  (drops BOM/NaN/comments; the parse is the sanitizer).
- returns the union of property names for the label/key field dropdowns.

### D4. Delivery: one gated endpoint, cached

`GET /surveys/<uuid>/layers/<int:layer_id>.geojson` (`views.py`):

- access = same gate as the survey section pages (published, or owner/test-link for
  drafts) — the reason a public storage URL is unacceptable.
- `ETag` from `updated_at`; `Cache-Control: private, max-age=300`. Respondent devices
  in one campaign hit it once per session in practice.
- layer metadata (id, name, color, label_field, show_popups, url) is inlined per page
  via `json_script` — it is tiny; only geometry goes through the endpoint.

### D5. Respondent rendering (inline JS next to the map init)

- `window._refLayers` built once at map init: per layer `fetch(url)` →
  `L.geoJSON(fc, {style, pointToLayer, onEachFeature})`, kept across section swaps
  (persistent map); `L.control.layers` gets them as overlays (control shown when
  basemap count > 1 OR layer count > 0).
- Styling: simplestyle properties (`stroke`, `fill`, `stroke-width`, `marker-color`,
  `stroke-opacity`, `fill-opacity`) win; layer `color` is the fallback (`fillOpacity`
  0.15, weight 2). Points render as small `circleMarker`s — no default markers that
  could be mistaken for answers.
- Labels: `label_field` set → permanent centered tooltip, **escaped** text
  (`bindTooltip` interprets HTML; property values are creator-file data).
- Interaction: `interactive: false` unless `show_popups`; popups render escaped
  `name`/`description`-style properties. Popup-enabled features must not swallow the
  draw flow: popups bind on click but geo placement taps go to the map (Leaflet click
  on a vector layer does not place a point today either — same as tapping a marker).
- Per-section visibility: `#section-data` gains `data-hidden-layers="[ids]"`;
  `initSection()` step: add/remove each `_refLayers` entry from the map accordingly.
  Overlay layers are inserted with a dedicated pane (`refLayersPane`, zIndex below
  markers) so answer geometry always draws on top.

### D6. Serialization

- Export: `survey.json` gains `layers: [{name, color, label_field, key_field,
  show_popups, position}]` (order = position) and the archive gains
  `layers/<position>.geojson` (written with `zf.writestr` from the DB text — no
  filesystem paths, S3-irrelevant by D1). `SurveySection` dict gains
  `hidden_layers: [positions]` (indexes into the layers array, not DB IDs).
- Import: recreate layers through the same `validate_layer_upload` path (AI generation
  and hand-made ZIPs get identical validation); remap position-indexes to new IDs for
  `hidden_layers`. Missing `layers/` entry → warning, layer skipped — never a hard
  error (matches `extract_structure_images` behavior). `_clean_layer_config()`
  whitelists keys and validates color, mirroring `_clean_style_settings`.

### D7. Editor endpoints (fetch-based, not the autosave form)

The layers card manages a collection — it does not fit `SurveyHeaderForm`'s
single-form autosave. Pattern: `editor_survey_thanks_image` (`editor_views.py:614`).

- `POST /editor/surveys/<uuid>/layers/` — multipart upload, returns layer JSON
  (+ `properties` for the field dropdowns) or 400 with a human message.
- `POST /editor/surveys/<uuid>/layers/<id>/` — config update (name, color,
  label_field, key_field, show_popups); server re-validates color `^#[0-9a-fA-F]{6}$`.
- `POST /editor/surveys/<uuid>/layers/<id>/delete/`.
- Section checklist saves inside the existing section form POST (`hidden_layers` as
  JSON list; unknown IDs dropped server-side).
- Owner-only (same role gate as survey settings).

### D8. Kill switch

`MAP_REFERENCE_LAYERS` env flag, default `True` (settings pattern of
`MOBILE_EDITOR_NAV`). Off: editor card and section checklist not rendered, respondent
metadata list empty, endpoints 404. Data stays in the DB — the flag only gates surfaces,
so flipping it back on after an incident loses nothing.

## Risks / Trade-offs

- **DB row size**: a 10 MB layer bloats the survey row set; acceptable for the model
  (few layers per survey), revisit if layers multiply. Mitigation: per-survey cap of
  5 layers.
- **Big layers on mobile**: 10 MB over cellular is slow; MVP accepts it (Olney's real
  file is ~150 KB) — cap + honest size display in the editor card; simplification is a
  named follow-up, not silently dropped.
- **Popup vs draw-tap interplay** is the riskiest UX spot; covered by an explicit spec
  scenario and manual mobile test before ship.

## Migration Plan

One additive migration (new model + section JSONField default `[]`). No data migration.
Before merge: `python manage.py showmigrations survey | tail` against master to dodge
parallel-worktree numbering collisions ([[feedback-parallel-migration-conflicts]]).

## Open Questions

None blocking. FD-14 linkage (key_field → choice codes UI) intentionally deferred.
