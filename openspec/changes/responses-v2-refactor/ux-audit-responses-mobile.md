# UX Audit — Responses tab on mobile (<768px)

Date: 2026-08-27 · Viewport tested: 390×844 (iPhone 14-class) · Survey: citypulse (65 sessions, 129 geo features) · Dev stand :8020, MOBILE_EDITOR_NAV on.

Context: creators actively use the Responses tab on phones to **monitor** results. The mobile job is "how is my survey doing right now", not deep data cleaning. Current implementation (PR #108 line): the bottom tab bar forces the desktop split-pane tree into a single leaf — the pane *contents* are desktop layouts, untouched.

## Findings

### F1 — Map pane renders an empty screen (severity: critical)
The Map pane shows only the "Response Map (129 features)" header; the Leaflet container collapses to 0 height. The `#data-split-container` chain (`calc(100vh - 100px)` minus the padding for the fixed bottom bar) loses its height on mobile, and `#analytics-map { flex:1 }` has nothing to fill. **The single most map-oriented product in the segment shows no map on a phone.**

### F2 — Table pane is unusable (critical)
At 390px the attribute table renders as a checkbox column + eye/trash actions; every data column is squeezed out. The Violations sidebar auto-expands and takes ~60% of the width. Toolbar buttons ("Hide fields", "Trash") wrap and clip. No horizontal-scroll affordance. A creator cannot answer "what did the last respondent say".

### F3 — Whole-page horizontal scroll (major)
`document.scrollWidth` = 543px vs 390px viewport (~40% overflow). Sources:
- Stat cards row (`.stat-cards` — flex, no wrap): the third card ("98% Completion Rate") is clipped, further cards fully off-screen.
- The Data/Performance tab row: version `<select>` + "Download data" button overflow right (a stray "D…" sliver is visible).
- Response Timeline range: two side-by-side `datetime-local` inputs wider than the viewport.
The whole page pans sideways under the finger; every scroll gesture fights it.

### F4 — Triple navigation, duplicated (major)
Visible at once: (1) level-1 page tabs Survey/Responses/Public results, (2) the Data/Performance sub-tab row, (3) the split-pane tabbar Table/Map/Charts **plus** split-right/split-down/close buttons, (4) the bottom bar Table/Map/Charts/Perf. Layers 2–3 duplicate layer 4 exactly; split/close buttons are meaningless on one-pane-at-a-time mobile. ~120px of vertical space (~15% of the viewport) is chrome before any data appears.

### F5 — No glanceable "how is it going" answer (major)
The monitoring question needs: total responses, delta ("+N today"), completion, a map thumbnail. Today the KPI cards are half off-screen (F3), the daily-trend chart is below the fold, and no delta is computed anywhere. The default Charts pane opens on clipped cards.

### F6 — Desktop-only controls survive on touch (minor)
Fullscreen toggles (`requestFullscreen` — unreliable on iOS Safari), column drag-grips, hover-only affordances (`.attr-th-sort` opacity), `confirm()` dialogs, 26px-high search inputs — all below the 44px touch minimum.

### F7 — Performance pane is near-OK (minor)
Section Funnel and Traffic Sources stack acceptably. Only the stat-cards overflow (same F3 cause) and small text sizes need fixing. Least-broken pane.

## What works
- The bottom tab bar itself: right vocabulary (Table/Map/Charts/Perf), right position, 48px targets.
- Charts pane content order (Overview → Timeline → per-question) matches the monitoring job.
- Question stat cards stack vertically and read fine.

## Layout variants proposed
See `mockups-responses-mobile.html` (three phone-frame variants):
1. **V1 «Monitoring feed»** — one scrollable pulse page: KPI 2×2 grid → map thumbnail → trend → per-question charts → recent responses. Bottom bar becomes Pulse/Map/Responses/Perf.
2. **V2 «Same panes, fixed»** — keep today's IA and bottom bar; strip duplicate chrome, fix each pane (map = full-height, table = card list, KPI = 2×2 grid). Smallest change.
3. **V3 «Map-first»** — the map is the home screen with KPI overlay chips and a draggable bottom sheet carrying charts/responses. Most differentiated, most work.
