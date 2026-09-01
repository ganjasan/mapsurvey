## Context

Reference layers (`SurveyMapLayer`) ship behind `MAP_REFERENCE_LAYERS`. Today three surfaces
render them: the respondent map (`base_survey_template.html` → `partials/reference_layers.html`),
the editor section preview (same shell), and nothing else. The Responses tab has three maps, all
built on `basemap_layers.html` or a bare tile layer:

| Surface | Template | Map var | Layers control |
|---|---|---|---|
| Map pane | `editor/partials/analytics_geo_map.html` | `map` (closure) → `window.analyticsMap` | `window._layersControl` from `basemap_layers.html` |
| Response modal | `analytics_dashboard_v2.html` (`sessionGeoOpenMap`) | `_sessionGeoMap`, rebuilt per open | none, own tile layer by design (5a in `session-geo-map-modal`) |
| Session mini-map | `editor/partials/analytics_session_detail.html` | `window._sessionMiniMap` | none |

`partials/reference_layers.html` is bare JS that assumes a `map` variable, a `ref-layers-data`
`json_script`, `window._layersControl`, and owns two globals (`window._refLayers`,
`window.applyRefLayerVisibility`). It cannot be included twice on one page without the second
include clobbering the first — the same constraint that made the modal build its own tile layer.

`survey_layer_geojson` delegates to `check_survey_access`, whose bypass is `editor`+. The
Responses tab is `viewer`+, and a closed survey returns a rendered "closed" page → the endpoint
turns that into 404 for everyone.

Constraints: no migrations; respondent page must stay byte-for-byte equivalent in behaviour
(`LayerRespondentRenderingTest`); the kill switch must hide the new surfaces; Django template
comments are single-line only (`{% comment %}` for blocks).

## Goals / Non-Goals

**Goals:**
- Map pane and response modal render every layer of the survey with respondent styling.
- Layers never interfere with the Responses map's own interaction (selection tools, feature
  popups, lasso).
- One source of truth for how a layer is styled; the respondent partial and Responses share it.
- Collaborators (`viewer`+) can fetch layers in every survey status; outsiders' rules unchanged.
- Geometry is fetched once per dashboard page load, not once per map.

**Non-Goals:**
- Per-section `hidden_layers` in Responses — the pane aggregates all sections.
- The session mini-map (200 px thumbnail).
- Public results page `/r/<slug>/`.
- Layer editing, filtering answers by zone (`key_field` consumer), the legacy `RESPONSES_V2=False`
  dashboard beyond what the shared `analytics_geo_map.html` partial gives it for free.

## Decisions

**1. Extract a layer factory, keep the respondent partial's state machine in place.**
New bare-JS partial `partials/ref_layer_factory.html` defines
`window.RefLayerFactory = { build(meta, featureCollection, opts) → L.GeoJSON }` carrying
`featureStyle`, the circle-marker `pointToLayer`, escaped permanent labels and the optional
popup. `opts.interactive` overrides `meta.show_popups`; `opts.pane` overrides `'refLayersPane'`.
`reference_layers.html` includes the factory and calls `build(meta, fc)` — its fetch loop,
per-section visibility and the respondent-toggle memory are untouched.
*Alternative rejected:* duplicating the ~40 lines of styling in `analytics_geo_map.html`. A
simplestyle fix would then need to land twice; the spec promises "the same styling".
*Alternative rejected:* making `reference_layers.html` itself re-entrant (parameterised map).
It owns page-level globals on purpose (layers survive HTMX section swaps); refitting that for a
dashboard that has no section navigation is more change for no gain.

**2. The Map pane owns loading; the modal reuses the cache.**
`analytics_geo_map.html` reads `ref-layers-data` (emitted by `analytics_dashboard_v2.html` via
`json_script`, same shape as the respondent shell, produced by `_build_map_layers_metadata`),
fetches each layer's GeoJSON once and stores `{meta, fc}` in `window._analyticsRefLayers`.
It builds a non-interactive overlay in a `refLayersPane` (z 350 — below the pane's answer panes
which start at 400) and adds it to `window._layersControl`, checked by default.
`sessionGeoOpenMap` iterates `window._analyticsRefLayers` and calls `RefLayerFactory.build`
against its fresh map, creating its own `refLayersPane` there. No new endpoint, no second
network request; if the pane's fetch has not finished when the modal opens, the modal simply
shows what has arrived (layers are context, not the response itself).
*Alternative rejected:* inlining geometry into the dashboard HTML. Up to 5 × 10 MB; the gated
endpoint exists precisely to keep geometry out of markup, and ETag revalidation makes the fetch
cheap on re-open.

**3. Layers are non-interactive on Responses.**
`build(meta, fc, {interactive: false})` regardless of `show_popups`. The pane's map click
handlers drive `SelectionManager` (pointer/lasso modes) and answer popups; an interactive
reference polygon under a cluster of points would swallow clicks meant for the points and
would open a popup that says nothing about responses. Creators already see the popup content
in the preview.

**4. Map renders when layers exist, even with zero geo answers.**
The pane's `if (!geoData.features.length) return;` becomes "return only when there are neither
features nor layers". The heading keeps `(0 features)`. This is what lets a creator check the
zones on the very map they will read answers from, before the first answer arrives. Every
downstream consumer of `geoData.features` already tolerates an empty array (it did on the
respondent side and the LayerManager iterates by slot).

**5. The endpoint grants collaborators, not the access-control module.**
In `survey_layer_geojson`: if the user is authenticated and `get_effective_survey_role` ranks
≥ `viewer`, skip `check_survey_access`. Everything else (anonymous, respondent with test link,
closed survey outsider) goes through `check_survey_access` exactly as before.
*Alternative rejected:* lowering the bypass in `check_survey_access` to `viewer`. That module
guards the respondent pages too; letting viewers *answer* a draft or a closed survey is a
separate product decision this change must not make implicitly.
Cache headers stay `private`, so a viewer's copy never serves an outsider.

**6. Kill switch is enforced server-side.**
`analytics_dashboard` passes `map_layers=[]` when the flag is off (through
`_build_map_layers_metadata`, which already does that), and the `json_script`/includes are
wrapped so no factory or loader script is emitted. Flag off ⇒ Responses HTML contains no layer
metadata and no layer URL; endpoint 404 is unchanged.

**7. The `_build_map_layers_metadata` helper moves to `survey/layers.py`.**
It is a pure function over a survey that two view modules now need; `views.py` keeps a
re-export so the respondent import path does not change. Alternative — importing
`survey.views` from `analytics_views` — drags the whole respondent module in for one function.

**8. Labels are anchored at the bounds centre, and layers join the Responses map only once
it has a size** (both found in the browser pass, not at the desk).
A permanent Leaflet tooltip on a path is positioned once, at add time, from `getCenter()` —
a *projected* centroid. The Responses Map pane starts as a hidden 0×0 container and is only
`invalidateSize()`d when its tab opens, so every polygon label landed at the same garbage point
thousands of pixels off-screen and never moved (circle markers were fine: their tooltip is the
marker's own latlng). Two changes: the factory overrides `getCenter` on labelled paths with
`getBounds().getCenter()` — pure latlng arithmetic, correct in any map state — and the pane's
loader adds a layer only after `map.getSize()` is non-zero (or on the first `resize`). The
respondent map is visible at load and never hit this; a bbox centre and a centroid coincide
for the convex zones layers are made of, so the respondent page keeps its label positions.
*Alternative rejected:* re-opening tooltips on `resize`. Works, but leaves the first render wrong
and depends on the event firing after the container is actually laid out.

**9. The cap goes to 10, the per-layer limits stay.**
FD-1 capped a survey at 5 layers as a storage mitigation (GeoJSON lives in the DB row, 5 × 10 MB)
with "revisit if layers multiply" — a guess, not a product decision. With Responses now reading
answers against overlays, a realistic survey carries a boundary, zones, a route and stops at
once. 10 × 10 MB = 100 MB worst case per survey, still far below any real upload seen (Olney:
150 KB); the 10 MB / 5000-feature per-file limits are untouched. Moving geometry to private S3
remains the answer if a survey ever approaches the worst case.

**10. Reference layers are slots of the Map pane's `LayerManager`, not overlays of the Leaflet
control** (owner request 2026-09-01: manage them from the Layers panel, reorder, set opacity).
`LayerManager` already gives every slot its own pane and assigns z-indices from `_order`
(`_assignPaneZIndices`), the panel already drags rows with SortableJS and calls `reorder`, and
the heat slot already has a settings popover with sliders. A third slot type `reference`
therefore costs: `addReference(entry)` (own pane, appended at the bottom of the order, so
layers start beneath every answer layer), a `reference` branch in `setLayerVisible`,
`setReferenceOpacity(id, v)` and a legend row. This also closes the stacking hole found on the
stand — with one shared pane, z-order was fetch-completion order; with a pane per slot it is
the panel order, whatever the network did.
*Opacity is the pane's CSS `opacity`*, not a per-feature `setStyle`: simplestyle files carry
their own per-feature `fill-opacity`/`stroke-opacity`, and scaling those would need the original
values kept per feature. One style property on the pane element dims the whole layer uniformly
and leaves the file's relative styling intact. Labels live in Leaflet's tooltip pane and stay
readable at any opacity — that is the point of a label.
*Persistence is client-side*: `localStorage['rv2RefLayers:<survey uuid>']` = `{order, hidden,
opacity}`, applied as layers arrive and saved on every change. Nothing reaches the server, the
respondent map and the editor preview are untouched, and the `position` field keeps its meaning
for them. Making order/opacity survey-level properties is a separate change (needs an owner
endpoint, a migration, ZIP round-trip and a permissions answer for viewers).
*The panel keeps reference layers in their own titled group* beneath the answer rows (owner
request 2026-09-01: tell what respondents drew from what the survey was set up with). Two
SortableJS lists rather than one with a divider: a divider inside a single list drifts as rows
are dragged past it, and the group also encodes the rule that reference material never rises
above an answer layer — the order fed to `LayerManager` is always answers, then the group.
Rows carry a square colour swatch (answers use a geometry glyph) and a muted label.
*The response modal reads the same slots*: hidden layers are skipped, opacity is applied to its
pane, and layers are added bottom-to-top in panel order.
*Alternative rejected:* keeping the Leaflet overlays control and adding a second reorder UI to
it. Two controls for one concept, and Leaflet's control cannot reorder or dim.

**11. Zero-answer fit follows the union of layers.** With several layers in different places, a
fit to the first arrival hides the rest; the loader extends one bounds object with every
arriving layer and refits until the creator moves the map themselves.

## Risks / Trade-offs

- [Extracting the factory changes respondent JS] → behaviour-preserving refactor; existing
  `LayerRespondentRenderingTest`/`LayerPreviewTest` assert the rendered markup and metadata,
  and a browser pass on a survey with a self-styled layer + labels is part of verification.
- [Modal opens before layer geometry arrived] → it shows what is cached; nothing errors.
  Accepted: the modal is a look at one response, layers are context.
- [Large layers (5 × 10 MB) on the dashboard] → same cost the respondent already pays; fetched
  once per page load, ETag 304 on revisit within the cache window.
- [Layer polygon fill hides heat-map / cluster readability] → creator toggles the overlay off
  in the layers control; default fill opacity is 0.15.
- [Legacy `RESPONSES_V2=False` template] → it includes the same `analytics_geo_map.html` partial,
  so the pane works there too, but the modal does not exist there. `json_script` emission goes
  into both dashboard templates so the legacy path does not break on a missing element.
- [Viewer role now sees draft layers] → viewers already see draft *answers* on this tab; a
  reference layer is the creator's own upload, less sensitive than the responses beside it.

## Migration Plan

No schema change. Ship behind the existing `MAP_REFERENCE_LAYERS` flag; turning it off
restores the pre-change Responses page. No data backfill.

## Open Questions

- None blocking. Whether `/r/<slug>/` should show layers is a separate change (public audience,
  possibly a per-layer "public" toggle).
