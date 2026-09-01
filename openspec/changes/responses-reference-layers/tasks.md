## 1. Endpoint access for collaborators

- [x] 1.1 In `survey/views.py::survey_layer_geojson`, skip `check_survey_access` when the request user is authenticated and `get_effective_survey_role(user, survey)` ranks ≥ `viewer` (import `SURVEY_ROLE_RANK` / `get_effective_survey_role` from `survey/permissions.py`); keep every other path unchanged
- [x] 1.2 Tests in `LayerEndpointTest`: viewer on draft → 200 with `private` cache; owner on closed → 200; anonymous on closed → 404; authenticated user with no role on closed → 404 (GIVEN/WHEN/THEN docstrings)

## 2. Shared layer factory

- [x] 2.1 Create `survey/templates/partials/ref_layer_factory.html` — bare JS defining `window.RefLayerFactory.build(meta, featureCollection, opts)` with `featureStyle`, circle-marker `pointToLayer`, escaped permanent labels and the optional popup, honouring `opts.interactive` and `opts.pane`; a `{% comment %}` header (never multi-line `{# #}`)
- [x] 2.2 Rewrite `partials/reference_layers.html` to include the factory and call `RefLayerFactory.build(meta, fc)`; the fetch loop, pane creation, per-section visibility and the respondent toggle memory stay as they are
- [x] 2.3 Run `LayerRespondentRenderingTest` and `LayerPreviewTest`; open a testing-status survey with a self-styled layer + label field in the browser and confirm styling, labels and popups are unchanged

## 3. Metadata plumbing

- [x] 3.1 Move `_build_map_layers_metadata` to `survey/layers.py` as `build_map_layers_metadata(survey)`; keep a re-export under the old name in `survey/views.py`
- [x] 3.2 In `analytics_views.py::analytics_dashboard`, add `'map_layers': build_map_layers_metadata(survey)` to the context (empty list when the flag is off — the helper already does that)
- [x] 3.3 Emit `{{ map_layers|json_script:"ref-layers-data" }}` in both `analytics_dashboard_v2.html` and the legacy `analytics_dashboard.html`, wrapped in `{% if map_layers %}` together with the factory include

## 4. Responses Map pane

- [x] 4.1 In `analytics_geo_map.html`, change the early return to bail only when there are neither geo features nor entries in `ref-layers-data`
- [x] 4.2 After the `basemap_layers.html` include: create `refLayersPane` (z-index 350), read `ref-layers-data`, fetch each layer once, store `{meta, fc}` in `window._analyticsRefLayers`, build with `RefLayerFactory.build(meta, fc, {interactive: false, pane: 'refLayersPane'})`, add to the map and to `window._layersControl.addOverlay(layer, escapedName)`; `console.warn` on fetch failure
- [x] 4.3 Verify in the browser: zones beneath points, control lists the layer checked, pointer/lasso selection over a zone still selects answers, heat-map toggle unaffected, a section-hidden layer still shows

## 5. Response map modal

- [x] 5.1 In `analytics_dashboard_v2.html::sessionGeoOpenMap`, after the tile layer: create `refLayersPane` on the modal map and add `RefLayerFactory.build(entry.meta, entry.fc, {interactive:false, pane:'refLayersPane'})` for every entry in `window._analyticsRefLayers` that has geometry
- [x] 5.2 Verify in the browser: open a response's full-size map, layer renders beneath the response geometry, Network tab shows no new `/layers/` request; the drawer mini-map stays bare

## 6. Tests for the dashboard

- [x] 6.1 `AnalyticsReferenceLayerTest`: owner opens the dashboard of a survey with a layer → response contains `ref-layers-data` with the layer's id/name/url and does NOT contain the layer's geometry coordinates
- [x] 6.2 Same test class, `@override_settings(MAP_REFERENCE_LAYERS=False)` → no `ref-layers-data`, no layer URL in the HTML
- [x] 6.3 Viewer opens the dashboard of a draft survey with a layer → metadata present (pairs with 1.2 so the whole path works for viewers)
- [x] 6.4 Run the template-comment guard test and the full `survey` suite once; record the delta

## 7. Layer cap 5 → 10

- [x] 7.1 `MAX_LAYERS_PER_SURVEY = 10` in `survey/layers.py`; editor help text and its 12 locale catalogs say "max 10 layers"
- [x] 7.2 Test in `LayerEditorTest`: 10 layers exist → the 11th upload is refused with the limit message and the count stays 10

## 8. Layers panel: reference slots, order, opacity

- [x] 8.1 `LayerManager.addReference(entry)` (own pane, appended at the bottom of `_order`), `reference` branch in `setLayerVisible`, `setReferenceOpacity(id, v)` via pane CSS opacity
- [x] 8.2 Loader hands arriving layers to `addReference` instead of `_layersControl.addOverlay`; legend row for `reference` slots in a titled "Reference layers" group (own SortableJS list beneath the answers) (handle, checkbox, swatch, name/zoom-to, crosshair, opacity button → popover with one slider)
- [x] 8.3 Prefs in `localStorage['rv2RefLayers:<uuid>']` — `{order, hidden, opacity}` applied on arrival, saved on every change (reorder hook, checkbox, slider)
- [x] 8.4 Zero-answer fit extends bounds with every arriving layer and refits until the creator moves the map
- [x] 8.5 Modal applies the slots' visibility, order and opacity
- [x] 8.6 Browser check on the stand: 8 layers listed beneath answer layers; boundary at the bottom whatever arrives first; drag to top → on top; slider dims only that layer; reload keeps both; respondent page unaffected

## 9. Wrap-up

- [x] 9.1 Update `CLAUDE.md` architecture notes: reference layers render on respondent, preview, Responses Map pane and response modal; factory partial is the single styling source; viewer+ bypass on the layer endpoint
- [x] 9.2 `openspec validate responses-reference-layers --strict`
