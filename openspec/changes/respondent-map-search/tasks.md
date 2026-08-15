# Tasks

## 1. Shared geocoding client and control

- [x] 1.1 Add `survey/assets/js/components/map_place_search.js` exposing a single
      `MapPlaceSearch.attach(map, options)` that mounts a Leaflet control and returns a handle.
      `options.onSelect(feature)` lets a caller react to a chosen place; default behaviour moves the
      map only.
- [x] 1.2 Geocoding call: `GET https://api.mapbox.com/search/geocode/v6/forward` with `q`,
      `access_token`, `limit=5`, `language`, `proximity` from the current map centre; `permanent`
      left at its default `false`. Keep it in one function — the provider swap must be local.
- [x] 1.3 Throttling: 3-character minimum, 300ms debounce, per-page in-memory cache keyed by
      `(query, rounded proximity)`, `AbortController` cancelling the superseded request.
- [x] 1.4 Result selection: `fitBounds` on `properties.bbox` when present, else `flyTo` with a zoom
      derived from `properties.feature_type`. Never place a marker, never touch a form field.
- [x] 1.5 Return no control at all when the access token is empty.
- [x] 1.6 Keyboard and screen-reader behaviour: arrow keys and Enter over the result list, Escape
      closes it, the input labelled, the list announced. Accessibility is procurement-relevant in
      Germany (`docs/marketing/user-outreach/mw_think_jena/2026-07-31_call-notes.md:143`).
- [x] 1.7 Error path: a failed or empty geocoding response shows an inline message in the result
      list and leaves the map where it is. No alert, no console-only failure.

## 2. Styling

- [x] 2.1 Control styles in `survey/assets/css/main.css`, matching the editor's existing
      `.map-search` look (rounded input, leading magnifier icon, accent focus ring) so the two
      surfaces stay visually identical.
- [x] 2.2 Desktop: mounted `topleft`, offset clear of the 420px `#info_page` sidebar, following the
      sidebar's show/hide transition.
- [x] 2.3 Mobile (`max-width: 768px`): collapsed to an icon that expands to a full-width input;
      must not overlap the drawbar or the crosshair overlay.

## 3. Respondent map

- [x] 3.1 Mount the control in `survey/templates/base_survey_template.html` after map init (near the
      `LocateControl` at line 201), passing the active language.
- [x] 3.2 Verify it survives HTMX section navigation — the map persists across sections
      (`persistent-map-htmx-navigation`), so the control must mount once and not duplicate.
- [x] 3.3 Verify no interaction with draw mode, crosshair mode, or an in-progress edit: searching
      while a shape is being drawn moves the map without cancelling the draw.

## 4. Editor: move off Nominatim

- [x] 4.1 Remove the inline Nominatim search from `survey/templates/editor/survey_create.html`
      (styles at 36-42, markup at 114-117, script at 270-292).
- [x] 4.2 Mount the shared control on the creation map; keep the existing rule that the map centre
      is the start position, so framing by search still sets it.
- [x] 4.3 Confirm no other template calls Nominatim: `grep -rn nominatim` over templates and assets
      returns nothing.

## 5. Spec reconciliation

- [x] 5.1 Amend the stale geocoder claim in `simplify-survey-create`'s delta —
      `specs/survey-editor/spec.md:49-52` says "no API key required — OpenStreetMap Nominatim". If
      that change has already archived, amend the main `survey-editor` spec instead.

## 6. Verification

- [x] 6.1 `python manage.py collectstatic` (never edit `staticfiles/` directly).
- [x] 6.2 `./run_tests.sh survey` — baseline before, once after. No loop.
- [x] 6.3 Manual pass in the browser on a real survey: search a city, search an address, search
      nonsense, search with the sidebar hidden, on desktop and at mobile width.
- [x] 6.4 Manual pass with `MAPBOX_ACCESS_TOKEN` emptied: no control, no console errors.
- [x] 6.5 Confirm in devtools that typing a query fires one request, not one per keystroke.
