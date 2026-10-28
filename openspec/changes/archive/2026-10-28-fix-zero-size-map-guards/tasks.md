# Tasks: fix-zero-size-map-guards

## 1. Respondent map

- [x] 1.1 `mapHasSize()` + `moveMapTo(lat, lng, zoom)` in `base_survey_template.html`: reject non-finite values, remember the target when the container has no size
- [x] 1.2 `locateUser()` routes its success callback through `moveMapTo` and skips the marker work when the move was deferred
- [x] 1.3 The section-transition fly routes through `moveMapTo` too — it checked its inputs for `NaN` but not the container, which is the case that fired
- [x] 1.4 Replay the pending target immediately after the existing `invalidateSize()` in `initSection()`

## 2. Analytics heat layer

- [x] 2.1 `_guardHeatRedraw()` in `editor/partials/analytics_geo_map.html` wraps `_redraw` to return early on a `0×0` canvas
- [x] 2.2 Apply it where the layer is created, so both dashboards and all sixteen `invalidateSize()` callers are covered
- [x] 2.3 Leave `public_results.html` alone — visible map, bounds already in `try/catch`, no reported error

## 3. Tests

- [x] 3.1 Respondent page renders the guard and routes both fly paths through it — assert on markup, since the Django test client runs no JavaScript
- [x] 3.2 Assert no `map.flyTo(` call remains outside `moveMapTo`, so a new unguarded move fails the build
- [x] 3.3 Analytics page renders `_guardHeatRedraw` and applies it to the created layer
- [x] 3.4 Ordinary respondent rendering is unchanged (map section still carries its coordinates)

## 4. Verification

- [x] 4.1 `./run_tests.sh survey` — compare against the 1765-test / OK baseline
- [x] 4.2 Browser pass: load a survey preview, trigger locate on a form section, confirm no console error and that the position lands when the map section returns. The markup tests cannot see this
- [ ] 4.3 After merge + deploy, mark PostHog issues `01a03018-74ba`, `01a03018-74bb`, `01a04e54` resolved
