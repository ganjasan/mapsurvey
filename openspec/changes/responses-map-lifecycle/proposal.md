## Why

On 2026-09-15 at 00:25 UTC a creator on `/editor/surveys/747d340a…/analytics/#map` produced
three PostHog issues in five seconds, all from the same function:

| 00:25:00 | `TypeError: Cannot read properties of undefined (reading 'min')` — `Polygon._clipPoints` via `Map.whenReady → addLayer` | [`01a0a273-f54f`](https://eu.posthog.com/project/248938/error_tracking/01a0a273-f54f-7062-b55c-cac694528c32) |
| 00:25:04 | `TypeError: Cannot read properties of undefined (reading 'parentNode')` — `initMiniMap → Map.remove → … → SVG._removePath` | [`01a0a273-ffeb…83`](https://eu.posthog.com/project/248938/error_tracking/01a0a273-ffeb-7d81-9d4a-d914b3e78383) |
| 00:25:05 | `Error: Map container is being reused by another instance` — `htmx swap → initMiniMap → Map.remove` | [`01a0a273-ffeb…57`](https://eu.posthog.com/project/248938/error_tracking/01a0a273-ffeb-7d81-9d4a-d924b70f9257) |

It came back on 2026-09-26 while this change sat unmerged: one creator (Firefox 156) produced 32
events in eight minutes (16:57–17:06 UTC), spread over seven issues because Firefox words the
TypeErrors differently — `Map container is being reused by another instance`
[`01a0dea7-0496`](https://eu.posthog.com/project/248938/error_tracking/01a0dea7-0496-7521-a0ec-752a50208f03) ×16 and
[`01a0dea9-3e42`](https://eu.posthog.com/project/248938/error_tracking/01a0dea9-3e42-7401-9b97-fca5ed24d0d2) ×7;
`can't access property "min", t is undefined`
[`01a0dea6-71ba`](https://eu.posthog.com/project/248938/error_tracking/01a0dea6-71ba-7640-8dff-9975ffc8cb76) ×3 and
[`01a0dea9-1fac`](https://eu.posthog.com/project/248938/error_tracking/01a0dea9-1fac-7172-b463-036477fb3992) ×2;
`can't access property "parentNode", t is undefined`
[`01a0dea6-8859`](https://eu.posthog.com/project/248938/error_tracking/01a0dea6-8859-7120-85ab-12c413ceab03) ×2,
[`01a0dead-8861`](https://eu.posthog.com/project/248938/error_tracking/01a0dead-8861-7123-9c0d-025147f995cb) ×1,
[`01a0dea9-31df`](https://eu.posthog.com/project/248938/error_tracking/01a0dea9-31df-7581-8d1d-8278f4d94ee1) ×1.
Sixteen repeats of the same `remove()` from one person is the "every further open throws" loop
below, observed: the preview stayed blank until a page reload.

That is one defect unfolding, not three. `initMiniMap` in
`editor/partials/analytics_session_detail.html` is the 200-px map in the response drawer. It runs
every time the drawer's partial is swapped in — every response the creator opens — and does two
things wrong:

1. **It adds layers to a map whose container has no size.** The drawer is an overlay below 1200px
   and full-screen below 768px; the partial's script runs at swap time, before layout. Leaflet's
   renderer never gets `_bounds`, and the first polygon throws `reading 'min'`. That polygon is now
   half-attached: it has no `_path`.
2. **It keeps the map in `window._sessionMiniMap` and calls `.remove()` on it at the next open.**
   By then HTMX has thrown the old DOM away. Leaflet 1.4's `Map.remove()` deletes the container's
   `_leaflet_id` *first*, then removes each layer — and the half-attached polygon throws
   `reading 'parentNode'`. The `= null` after `remove()` never runs, so the third open calls
   `remove()` on the same instance again, and this time the `_leaflet_id` check fails:
   *"Map container is being reused by another instance"*. Every further open in that session
   throws before it draws anything.

The same shape appears three more times on the Responses page. Four maps — the Map pane
(`analytics-map`), the Overview thumbnail (`rv2-ov-map`), the drawer mini-map
(`session-mini-map`) and the response modal (`session-geo-modal-map`) — each carry a private
answer to the same three questions: *is there already a map in this container? how do I get rid
of it? when is the container big enough to draw into?* The thumbnail guesses with
`setTimeout(150)`, the Map pane with `invalidateSize()` "called from sixteen places" (its own
comment), the modal waits for `shown.bs.modal`, the drawer does nothing and gets the errors above.

This is the class #194 fixed on the editor's map pickers (`map_position_picker.js` got `detach()`
on `htmx:beforeCleanupElement`) and the third time in this project a JavaScript global has
outlived the DOM it pointed at. `fix-zero-size-map-guards` guarded *drawing* into a 0×0 map on two
surfaces; nothing guards *mounting* one.

Now, because the drawer is the daily surface of Responses v2 — every creator reading answers goes
through it — and because the next map added to this page will copy one of the four patterns.

## What Changes

- **One mount helper for editor maps** — `survey/assets/js/editor_map.js`, global `EditorMap`,
  loaded from `editor_base.html` next to `map_position_picker.js`:
  - `EditorMap.mount(container, leafletOptions, ready)` creates the map, keeps the instance **on
    the element** (never in a global), disposes any map already there, and runs `ready(map)` only
    once the container has a non-zero size.
  - `EditorMap.dispose(container)` never throws and always leaves the container mountable again:
    `_leaflet_id` cleared, Leaflet's classes and panes gone, the registry entry dropped.
  - A mounted map disposes itself on `htmx:beforeCleanupElement`; a registry sweep at every mount
    catches instances whose element left the document by any other route.
- **The four Responses maps mount through it.** The drawer mini-map loses its modal/drawer
  branching, its global and its unused `initSessionMiniMap` export; the thumbnail loses
  `setTimeout(150)`; the modal keeps its Bootstrap hooks but disposes through the helper; the Map
  pane changes only its mount line (its `LayerManager` is out of scope).
- **A class-level guard.** A source scan asserts that no analytics template calls `L.map(`
  directly, so the fifth map cannot skip the helper; source assertions pin the helper's contract
  (never-throwing dispose, `_leaflet_id` cleared, cleanup hook registered) the way
  `MapPickerAutosaveTeardownGuardTest` pins the picker's.

## Impact

- Affected specs: `analytics-data-workspace` (new requirement), `responses-detail-drawer`,
  `responses-overview` (scenarios added to existing requirements)
- Affected code: new `survey/assets/js/editor_map.js`; `editor/editor_base.html`;
  `editor/partials/analytics_session_detail.html`, `editor/partials/analytics_overview_pane.html`,
  `editor/partials/analytics_geo_map.html`, `editor/analytics_dashboard_v2.html`; `survey/tests.py`
- No migration, no kill switch — rollback is a revert. `window.analyticsMap` and
  `window._rv2OverviewMap` stay: sixteen `invalidateSize()` callers read them and they are not what
  broke. Only `window._sessionMiniMap` goes, because it is the global that outlived its DOM.
- Out of scope: the editor's map pickers (`#192`/`#194` own their lifecycle through
  `MapPositionPicker`), the layer object editor, the respondent map, `public_results.html`.
