# Proposal: fix-zero-size-map-guards

## Why

Leaflet computes everything from `map.getSize()`. When the container is hidden or has not been laid
out yet, that size is `0×0`, and every projection built on it degenerates:

- `map.flyTo(...)` unprojects through a zero size and produces `LatLng(NaN, NaN)`, which Leaflet
  rejects by throwing.
- `leaflet.heat` redraws into a `0×0` canvas and `getImageData` throws `IndexSizeError`.

Two PostHog issues, same root cause on two different surfaces:

**Respondent / preview — 72 events across two fingerprints**
([`01a03018-74ba`](https://eu.posthog.com/project/248938/error_tracking/01a03018-74ba-7093-9d16-31dea6ed041a),
[`01a03018-74bb`](https://eu.posthog.com/project/248938/error_tracking/01a03018-74bb-7cf1-9845-fa90643fdd33)).
The stack names the caller:

```
navigator.geolocation.getCurrentPosition.enableHighAccuracy
  → e.flyTo → e.unproject → Object.pointToLatLng → new M → Error: Invalid LatLng object: (NaN, NaN)
```

`locateUser()` in `base_survey_template.html` calls `map.flyTo(...)` straight from the geolocation
success callback. That callback lands whenever the device answers — up to ten seconds later, by
which time the respondent may have advanced to a `form` section, where the `survey-form-layout`
body class hides `#map` entirely. The map is then `0×0` and the fly throws. `flyTo` is animated, so
it throws once per animation frame: 64 events came from 3 sessions.

**Editor analytics — 1 event**
([`01a04e54`](https://eu.posthog.com/project/248938/error_tracking/01a04e54-62fd-7731-beca-593e29ef8d45)):

```
e.invalidateSize → e.fire → e._reset → e._redraw → t.draw → IndexSizeError: source width is 0
```

on `/editor/surveys/<uuid>/analytics/#responses`. `invalidateSize()` is called from **sixteen
places** across the analytics templates — pane switches, drag-resize, modal opens, layout changes,
the v1 and v2 dashboards, the filter and table engines — and not one of them checks that the pane is
visible. On a hidden pane the call re-fires the heat layer's redraw against a `0×0` canvas.

The respondent template already knows about this class of bug: `initSection()` calls
`invalidateSize()` after a swap precisely "to repair the dimensions Leaflet measured while the
container was `display:none`". The repair exists; nothing stops the *moves* that happen before it.

## What Changes

- **A `mapHasSize()` guard on both surfaces**, checking `getSize()` is non-zero before anything is
  asked of the projection.
- **Respondent (`base_survey_template.html`)**:
  - `locateUser()` ignores non-finite coordinates, and when the map has no size it **remembers the
    target instead of flying to it**. The respondent asked to be located; silently doing nothing
    would be a worse answer than doing it late.
  - The pending target is applied right after the existing `invalidateSize()` in `initSection()`,
    which is exactly the moment the container regains its size.
  - The section-transition `flyTo` gets the same size check (it already checks for `NaN` inputs, but
    not for a zero-size container, which is the case that actually fired).
- **Editor (`editor/partials/analytics_geo_map.html`)**: the guard goes on the **heat layer**, not on
  the callers. `_redraw` returns early while its canvas is `0×0`. Sixteen call sites would be
  sixteen chances to miss one — and would not cover the seventeenth. One layer-level guard covers
  every caller in both dashboards, present and future.

`public_results.html` also builds a heat layer. It is left alone: its map is on a visible page, its
bounds work is already wrapped in `try/catch`, and no error has ever been reported there. Guarding it
would be a change without evidence.

The two guards are inlined on their own surfaces rather than shared through a static file. The pages
have no common bundle, and adding a request to the respondent page for a few lines is the wrong trade
against `loadtest/`'s findings. Each copy carries a comment naming the other.

## Capabilities

### Modified Capabilities

- `marker-draw-lifecycle`: the respondent map is never driven while its container has no size, and a
  geolocation result that arrives while the map is hidden is applied when it returns.
- `analytics-data-workspace`: the heat layer does not draw while its canvas has no size, whichever
  of the many resize paths woke it.

## Impact

- **Code**: `survey/templates/base_survey_template.html`,
  `survey/templates/editor/partials/analytics_geo_map.html`, tests in `survey/tests.py`.
- **No migrations, no settings, no Python changes.**
- **Behaviour change, deliberate**: a locate result that arrives while the map is hidden now moves
  the map when it comes back, instead of throwing. If the section that brings the map back declares
  its own start position, that position wins and the deferred locate is dropped — an explicit
  section view outranks a stale locate request. The location marker is not placed for a deferred
  result either; placing it would mean projecting on a zero-size map, which is the bug.
- **Testing limits, stated plainly**: this is browser geometry that the Django test client cannot
  execute. The tests assert the guard is present and that no unguarded call path exists — a
  markup-level check in the spirit of `lesson_test_client_misses_html5_validation`.

**Verified in a real browser** on the dev stand, which is what actually closes this:

| | on the form section | after the swap |
|---|---|---|
| `map.getSize()` | `0×0` | `1854×961` |
| raw `map.flyTo(...)` | `Error: Invalid LatLng object: (NaN, NaN)` — the production error, reproduced | — |
| `moveMapTo(...)` | returns `false`, throws nothing, defers | — |
| `flyTo` calls | 0 | 1, with the section's own `[52.516, 13.377, 14]` |
| deferred target | stored | consumed |
| page errors | 0 | 0 |

One caveat on that pass: the automation tab is backgrounded, so `requestAnimationFrame` is paused
(measured: 0 ticks per second) and `flyTo`'s animation never advances. The camera therefore does not
visibly land in the harness. `setView` — which uses no animation frames — moves the map correctly,
and the spy above proves `flyTo` is invoked with the right arguments, so the wiring is confirmed even
though the final camera position is not observable there.
