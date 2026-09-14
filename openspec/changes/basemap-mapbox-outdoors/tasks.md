## 1. Settings and context

- [x] 1.1 Add `MAPBOX_OUTDOORS_URL` to `mapsurvey/settings.py` next to `MAPBOX_URL`, defaulting to
      `https://api.mapbox.com/styles/v1/mapbox/outdoors-v12/tiles/256/{z}/{x}/{y}@2x?access_token={accessToken}`
- [x] 1.2 Return `MAPBOX_OUTDOORS_URL` from `survey.context_processors.mapbox()`
- [x] 1.3 Document `MAPBOX_OUTDOORS_URL` in `.env.example` as optional (default is the production value)

## 2. Shared basemap partial

- [x] 2.1 In `partials/basemap_layers.html`, read `{{ MAPBOX_URL }}`, `{{ MAPBOX_OUTDOORS_URL }}` and
      `{{ MAPBOX_ACCESS_TOKEN }}` from the template context instead of the enclosing `mapboxUrl` /
      `mapboxAccessToken` JS variables
- [x] 2.2 Point `topo` at the Outdoors URL: `maxZoom: 22`, `accessToken`, attribution
      `© Mapbox © OpenStreetMap`; drop the OpenTopoMap URL and attribution
- [x] 2.3 Add a comment stating the partial is self-contained and why (a new including template must
      not have to remember to declare variables first)
- [x] 2.4 Delete the now-dead `var mapboxUrl` / `var mapboxAccessToken` declarations in
      `base_survey_template.html`, `editor/partials/analytics_geo_map.html`,
      `editor/partials/analytics_session_detail.html`, `editor/partials/section_map_picker.html` —
      grep each file first to confirm nothing else reads them

## 3. Surfaces with their own provider tables

- [x] 3.1 `editor/survey_create.html`: `topo` uses `{{ MAPBOX_OUTDOORS_URL }}` with the access token,
      `maxZoom: 22`, Mapbox + OpenStreetMap attribution
- [x] 3.2 `public_results.html`: `streets` uses `{{ MAPBOX_URL }}`, `topo` uses
      `{{ MAPBOX_OUTDOORS_URL }}`, both with `accessToken` and Mapbox + OpenStreetMap attribution;
      `satellite` (Esri) unchanged
- [x] 3.3 `public_results.html`: replace the stale "no Mapbox token needed on the public page"
      comment — the `pk.` token is already public on every respondent page

## 4. Tests

- [x] 4.1 Update the existing topo tile-URL test in `survey/tests.py` (asserts
      `tile.opentopomap.org`) to assert the Mapbox Outdoors URL instead
- [x] 4.2 Add a guard test: respondent section page with all three basemaps contains neither
      `tile.openstreetmap.org` nor `tile.opentopomap.org`
- [x] 4.3 Add the same guard for the public results page (`/r/<slug>/`) with a map block
- [x] 4.4 Add a test that overriding `MAPBOX_OUTDOORS_URL` (via `override_settings`) changes the
      rendered topo tile URL, proving no template literal remains
- [x] 4.5 Run `./run_tests.sh survey -v2` and confirm no regressions

## 5. Verify in a browser

- [x] 5.1 Run the dev server, open a survey with `topo` enabled, switch the basemap and confirm
      Mapbox Outdoors tiles render with the correct attribution
- [x] 5.2 Open the editor Response Map and the create wizard picker, switch to Topo, confirm the same
- [x] 5.3 Open a public results page with a map block, confirm no request goes to
      `tile.openstreetmap.org` (check the network panel, not just the rendered map)

## 6. Close the loop

- [ ] 6.1 After merge and deploy, verify Topo on production and reply to the reporting creator
      (`dawgranat@gmail.com`) — short, per the bug-fix email convention
