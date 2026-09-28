## Context

The Responses page (`analytics_dashboard_v2.html`, and `analytics_dashboard.html` when
`RESPONSES_V2` is off) shows geo answers in four Leaflet maps:

| Container | Surface | Mounted by | Lifecycle today |
|---|---|---|---|
| `analytics-map` | Map pane | `analytics_geo_map.html`, `DOMContentLoaded` | once; pane starts `hidden`; own `whenMapSized()` on `map.once('resize')`, fed by sixteen `invalidateSize()` callers |
| `rv2-ov-map` | Overview thumbnail | `analytics_overview_pane.html`, `initOverview()` | once (`initialized` flag); `setTimeout(150)` then `invalidateSize()` + `fitBounds` |
| `session-mini-map` | response drawer (v2) / modal body (v1) | `analytics_session_detail.html`, inline script at every HTMX swap | `window._sessionMiniMap.remove()` then `L.map()` again; v1 waits for `shown.bs.modal` |
| `session-geo-modal-map` | full-size response modal | `analytics_dashboard_v2.html`, `shown.bs.modal` | `_sessionGeoMap.remove()` on `hidden.bs.modal` |

Leaflet is 1.4.0. Its `Map.remove()` runs in this order: unbind events → compare
`_containerId` with `container._leaflet_id` (throw *"reused by another instance"* on mismatch) →
**delete `container._leaflet_id`** → stop, clear panes → `layer.remove()` for every layer → drop
references. A layer that throws during its own removal leaves the map in a state where the
`_leaflet_id` is already gone but the instance is still held — the exact state the PostHog
sequence shows. HTMX 1.9.10 fires `htmx:beforeCleanupElement` on every element it discards
during a swap, which `map_position_picker.js` already relies on.

### What the reproduction showed (task 1)

Instrumenting `L.Map.prototype.remove` / `_initContainer` / `getCenter` on the unfixed page and
opening eight responses in a row at 1280px, with 100–900 ms between opens:

- **Every** open called `remove()` on a map whose container was **already detached** — HTMX had
  swapped the partial before the script ran. That is the global outliving its DOM, on the happy
  path, not only when something has already gone wrong.
- 13 ms after one such remove/create pair, a listener still bound on the removed map fired and
  called `getCenter()` on it → `TypeError: Cannot read properties of undefined (reading
  '_leaflet_pos')` (`_mapPane` is gone). Leaflet 1.4's `remove()` does not fully unbind when the
  container is already out of the document. This symptom is not yet in PostHog; it is the same
  defect one step earlier.
- On this machine the container always had a size at swap time (the drawer is a sibling of the
  panes, laid out even on `#map`, at 1280/900/390), so the `reading 'min'` first step of the
  production cascade did not reproduce locally; the sequence that follows it did. The helper
  covers both regardless of which step a given browser hits first.

Consequence for D2/D3: disposal must happen **on `htmx:beforeCleanupElement`, while the element is
still attached** (HTMX fires it before `removeChild`), so Leaflet's own `remove()` runs against a
live container and unbinds what it bound. The registry sweep remains the net for detached
leftovers, and `dispose()` finishes the container by hand whatever `remove()` managed.

## Goals / Non-Goals

**Goals**

- Opening any number of responses in a row, on any viewport, mounts the mini-map cleanly every
  time and never throws in Leaflet.
- Nothing is drawn into a map whose container has no size, on any of the four surfaces, without
  each surface guessing a delay.
- A fifth map on this page cannot re-introduce a private lifecycle: the guard is on the class.

**Non-Goals**

- The `LayerManager`, heat layer, selection tools and reference-layer plumbing of the Map pane.
  Its mount line changes; its 1,300 lines do not.
- The editor's map pickers (`MapPositionPicker` owns their lifecycle since #192/#194), the layer
  object editor, the respondent map and `public_results.html`.
- Removing `window.analyticsMap` / `window._rv2OverviewMap`. Sixteen `invalidateSize()` callers
  read them and they are harmless; a global is only a bug when it outlives its element.

## Decisions

### D1 — A module, loaded once, not a partial

`survey/assets/js/editor_map.js` defines `window.EditorMap` and is included from
`editor_base.html` next to `map_position_picker.js`. The drawer partial arrives by HTMX swap and
runs its inline script at swap time; the helper must already exist then. Same reasoning
`editor_base.html` records for `map_place_search.js`.

### D2 — The instance lives on the element

`mount()` stores the map as `container._editorMap`. When HTMX discards the element, the reference
goes with it; there is nothing left to call `.remove()` on later. This is the one change that
makes the `parentNode` → `reused` cascade impossible rather than merely handled.

A module-level `Set` of live maps is the safety net beneath that: every `mount()` first sweeps it
and disposes any map whose container is no longer in the document. It covers removal paths that
do not go through HTMX (jQuery `.html()`, a future framework change) — a hook that silently stops
matching is how this class of defect returns.

### D3 — `dispose()` never throws and always leaves the container mountable

```
try { map.remove(); } catch (e) { /* half-torn map; finish by hand */ }
finally {
  delete container._leaflet_id;
  container.className = container.className.replace(/\bleaflet-\S+/g, '').trim();
  while (container.firstChild) container.removeChild(container.firstChild);
  container._editorMap = null; live.delete(map);
}
```

Leaflet's own `remove()` is the first attempt, because it also unbinds handlers and stops
animations. What follows makes the outcome independent of where `remove()` stopped: the id that
gates *"reused by another instance"* is gone, the panes it may have left behind are gone, and the
next `L.map()` on this element initialises from scratch. Errors inside `remove()` are swallowed
deliberately: the map is being thrown away, and an exception here is exactly what turned one bad
draw into a dead drawer for the rest of the session.

### D4 — `ready` runs when the container has a size, observed rather than timed

`mount()` returns the map immediately (callers that keep a reference still can) and calls
`ready(map)` once `getSize()` is non-zero, after an `invalidateSize()` so Leaflet's own
measurement matches. The wait uses `ResizeObserver` on the container; where it is unavailable, a
`requestAnimationFrame` loop polls `getSize()`. Both stop at the first non-zero size or at
dispose.

This replaces `setTimeout(150)` on the thumbnail and gives the mini-map what it never had. It does
not replace the Map pane's `whenMapSized()` — that helper answers a different question (it is
called per layer as they arrive asynchronously) and is out of scope.

A container that never gains a size (a drawer closed before it renders) keeps its observer until
the element is disposed. Nothing is drawn, nothing is leaked past the element's lifetime.

### D5 — What each surface keeps and what it loses

- **Drawer mini-map** — one `EditorMap.mount('session-mini-map', {…}, ready)`. The
  modal-or-drawer branching goes: the helper waits for size either way, and `shown.bs.modal` was
  only ever a proxy for "the container is laid out now". `window._sessionMiniMap` goes.
  `window.initSessionMiniMap` goes — no caller reads it (verified by grep across both dashboards
  and the table engine).
- **Overview thumbnail** — `EditorMap.mount(mapEl, {…}, ready)`; layer add and `fitBounds` move
  into `ready`; the 150 ms timer goes. `window._rv2OverviewMap` stays for its callers.
- **Response modal** — mount stays inside `shown.bs.modal` (Bootstrap's transition is a real
  animation, and the helper's wait would merely add a frame); `sessionGeoDestroy()` becomes
  `EditorMap.dispose('session-geo-modal-map')`; `_sessionGeoMap` goes.
- **Map pane** — `L.map('analytics-map', …)` becomes `EditorMap.mount('analytics-map', …)` so the
  registry knows it and the guard passes. Everything after that line is untouched.

### D6 — The guard scans the class, not the surfaces

Following the lesson recorded on #194 (a guard pinned to two URLs let the fourth map template ship
the same defect green), the test scans every analytics template's source — `editor/analytics_*.html`,
`editor/partials/analytics_*.html`, `editor/partials/_analytics_*.html` — and fails on any
`L.map(` outside `editor_map.js`. Rendering tests on both dashboards and on the detail endpoint
prove the helper is on the page and the four surfaces call it; source assertions on the helper pin
the contract of D2–D4 the way `MapPickerAutosaveTeardownGuardTest` pins the picker's.

There is no JavaScript test runner in this repository, so the behaviour itself is verified in a
browser (tasks 5.2–5.3) at the three drawer breakpoints.

## Risks / Trade-offs

- **`ResizeObserver` support.** Every browser a creator uses since 2020 has it; the rAF fallback
  exists for the rest and costs one frame per poll while a container is hidden.
- **Swallowed errors in `dispose()`.** A genuine new bug inside `Map.remove()` would be silent.
  Accepted: the alternative is the current behaviour, and PostHog error tracking would only show
  the symptom of a map being discarded, never a cause.
- **Map pane behaviour.** The one-line mount change must not alter `LayerManager` timing. The
  registry sweep runs on each mount and disposes only maps whose containers left the document;
  the Map pane's container never does.
- **v1 dashboard.** `RESPONSES_V2=False` still serves `analytics_dashboard.html` with the modal;
  the partial's new single mount path serves both because the helper waits for size instead of
  for `shown.bs.modal`. Covered by a rendering test under `override_settings(RESPONSES_V2=False)`.

## Migration Plan

None. Assets are versioned by the static manifest; a deploy serves the new hash.

## Open Questions

None blocking. Worth a backlog note: the Map pane's sixteen `invalidateSize()` callers could
collapse into a `ResizeObserver` on its container through the same helper, which is what D4 already
does for the other three maps. Separate change; larger blast radius.
