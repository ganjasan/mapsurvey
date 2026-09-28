## 1. Reproduce before fixing

- [x] 1.1 Seed a survey with a polygon answer and several responses; run the dev server; open Responses v2 at 1280px, open response A, then B, then C from the table and watch the console — record what fires and at which breakpoint (1280 / 900 overlay / 390 full-screen). The PostHog session had `#map` in the URL and its first error was `reading 'min'`, so also open a response from a map feature — *done with Playwright; findings recorded in design.md "What the reproduction showed"*
- [x] 1.2 Confirm in the console that the failing call is `initMiniMap` → `Map.remove()` and that `window._sessionMiniMap` is the instance whose container is no longer in the document — *confirmed: every open removed a detached container; a listener of the removed map then threw `reading '_leaflet_pos'`*

## 2. The helper

- [x] 2.1 `survey/assets/js/editor_map.js`: `EditorMap.mount(container, options, ready)`, `EditorMap.dispose(container)`, `EditorMap.get(container)`; instance on the element, live-map registry, sweep at mount
- [x] 2.2 `dispose()` per design D3: `try/catch` around `map.remove()`, then `_leaflet_id`, Leaflet classes and children cleared unconditionally
- [x] 2.3 `ready` per design D4: `ResizeObserver` with a `requestAnimationFrame` fallback; `invalidateSize()` before the callback; observer stopped at first size and at dispose
- [x] 2.4 `htmx:beforeCleanupElement` on the container disposes the map; cleanup also runs if the container is already detached when `mount()` is called for a sibling
- [x] 2.5 Load it from `editor_base.html` beside `map_position_picker.js`, with the same debug cache-buster

## 3. The four surfaces

- [x] 3.1 `analytics_session_detail.html`: one `EditorMap.mount('session-mini-map', …, ready)`; delete the modal/drawer branching, `window._sessionMiniMap`, `window.initSessionMiniMap`; layer loop and `fitBounds` move into `ready`
- [x] 3.2 `analytics_overview_pane.html`: mount through the helper; layer add and `fitBounds` into `ready`; drop `setTimeout(150)`; keep `window._rv2OverviewMap`
- [x] 3.3 `analytics_dashboard_v2.html`: modal map mounts through the helper inside `shown.bs.modal`; `sessionGeoDestroy()` → `EditorMap.dispose(…)`; drop `_sessionGeoMap`
- [x] 3.4 `analytics_geo_map.html`: `L.map('analytics-map', …)` → `EditorMap.mount('analytics-map', …)`; drop the `window._sessionMiniMap = null` line; nothing else
- [x] 3.5 `grep -rn "_sessionMiniMap\|initSessionMiniMap\|_sessionGeoMap"` across `survey/` returns nothing

## 4. Guards

- [x] 4.1 `EditorMapLifecycleGuardTest` (source scan): no `L.map(` in any `editor/analytics_*.html`, `editor/partials/analytics_*.html`, `editor/partials/_analytics_*.html`; run it BEFORE task 3 and confirm it names all four sites
- [x] 4.2 Source assertions on `editor_map.js`: `try {` around `.remove()`, `delete container._leaflet_id` outside the `try`, `htmx:beforeCleanupElement` registered, `ResizeObserver` referenced
- [x] 4.3 Rendering tests: v2 dashboard and v1 dashboard (`override_settings(RESPONSES_V2=False)`) both include `js/editor_map` and the Map pane / thumbnail call `EditorMap.mount`; the session detail endpoint renders `EditorMap.mount('session-mini-map'` and neither `_sessionMiniMap` nor `shown.bs.modal`
- [x] 4.4 Confirm 4.1 fails against the unfixed templates and passes after task 3

## 5. Verify and ship

- [x] 5.1 `./run_tests.sh survey -v2` — one run after the work; the baseline is the 2109/OK run from #195 earlier today — *2026-09-28 after rebase on #199: 2134 tests OK (skipped=1)*
- [x] 5.2 Browser at 1280px: open three responses in a row, prev/next, open the full-size modal, close, reopen; switch Overview → Map → Overview; zero console errors; the mini-map shows features every time
- [x] 5.3 Browser at 900px (overlay drawer) and 390px (full-screen drawer): same sequence — these are the viewports where the container is 0×0 at swap time
- [x] 5.4 `RESPONSES_V2=False` in the browser: the v1 modal's mini-map still renders once the modal is shown — *done 2026-09-28: ten sequential opens and seven opens 80 ms apart; mini-map drawn every time, zero page errors, no leaked containers*
- [x] 5.5 `openspec validate responses-map-lifecycle --strict`
- [x] 5.6 Open the PR against `master`; no migration, no kill switch — *PR #202, merged 2026-09-28*
- [x] 5.7 After deploy: resolve PostHog issues `01a0a273-f54f`, `01a0a273-ffeb…83`, `01a0a273-ffeb…57` and the seven Firefox issues of 2026-09-26 (`01a0dea7-0496`, `01a0dea9-3e42`, `01a0dea6-71ba`, `01a0dea9-1fac`, `01a0dea6-8859`, `01a0dead-8861`, `01a0dea9-31df`) once no new events arrive — *all ten resolved 2026-09-28 12:14 UTC, after editor_map.js was live on mapsurvey.org (12:12 UTC); PostHog reopens any that recur*
