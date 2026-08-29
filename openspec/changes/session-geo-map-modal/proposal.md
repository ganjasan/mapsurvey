## Why

A creator reading one response in Responses V2 cannot see where that respondent drew anything.
The drawer renders a geo answer as the bare string `point feature` — no coordinates, no preview,
no way to reach the map. The mini-map that used to serve this in the V1 modal is still in the
partial but is **dead code in V2**: `analytics_session_detail.html` initialises Leaflet from
`$('#sessionDetailModal').one('shown.bs.modal', initMiniMap)`, and `analytics_dashboard_v2.html`
contains no `#sessionDetailModal` at all (the partial is swapped into `#rv2-drawer-body`). The
selector matches an empty jQuery collection, the handler never fires, and the creator is left
with an empty 200px box below Notes.

So the capability regressed silently during the V1→V2 migration, and the owner reads the result
as "you can't look at a single session on a map" — which is accurate in effect.

## What Changes

- **Fix the regression**: initialise the session mini-map when the partial lands in the V2 drawer
  (HTMX swap on `#rv2-drawer-body`), not on a Bootstrap modal event that no longer exists. The
  V1 modal path, if still reachable, keeps working.
- **New: full-size session map modal.** A modal showing every geo object of ONE session at once —
  points, lines and polygons across all geo questions — with a per-question colour legend and
  click popups carrying the object's sub-answers (reusing the `attributes` payload that
  `responses-geo-subanswers` already ships).
- **Two entry points into that modal**, per owner decision:
  - clicking a geo answer row in the drawer (the row currently reading `point feature`);
  - clicking the mini-map preview in the drawer.
- **Geo rows become informative**: instead of the opaque `point feature`, the drawer row shows
  what the attribute table already shows (`39.71, −77.48`, `3 vertices`) and reads as clickable.
- **Regression guard**: a test asserting the drawer container the partial binds to actually
  exists in the dashboard template, so this class of "moved the markup, left the handler"
  breakage fails loudly instead of rendering an empty box.
- **Fix the workspace height so the drawer scrolls by itself.** `.rv2` used `min-height`, so the
  workspace grew with its own content and every `flex: 1; min-height: 0` below it constrained
  nothing: the drawer's `overflow-y: auto` never triggered, it scrolled with the page, and the
  responses table's footer was pushed past the viewport. Reported by the owner once the revived
  preview — which sits at the bottom of the drawer — made the behaviour visible.

Not in scope: filtering the main Map pane down to a single session, and any change to the
respondent-facing survey map.

## Capabilities

### New Capabilities
- `session-geo-map`: viewing all geo objects of a single response on a full-size map from the
  Responses drawer — the modal, its entry points, the legend, popups, and the drawer preview's
  initialisation contract.

### Modified Capabilities
- `responses-geo-subanswers`: the requirement "Session detail modal lists sub-answers per geo
  object" is written against the V1 modal, which V2 replaced with a drawer. Its wording moves to
  the drawer, and the numbered-object rule ("point feature 1/2") extends to the map modal's
  popups so an object on the map can be matched to its row.
- `responses-detail-drawer`: gains a requirement that the workspace fills the viewport and that
  the detail surface scrolls within its own bounds, keeping the table footer on screen. The
  original spec described the surface's placement per tier but never stated how it scrolls, which
  is why the layout could regress without contradicting anything written down.

## Impact

- `survey/templates/editor/partials/analytics_session_detail.html` — map initialisation, geo row
  markup and value formatting.
- `survey/templates/editor/analytics_dashboard_v2.html` — modal markup, open/close wiring,
  reuse of the existing basemap include.
- `survey/analytics_views.py` (`analytics_session_detail`) — may need no change: it already
  returns `geo_json` and `has_geo`. To be confirmed in design.
- `survey/tests.py` — regression guard plus coverage of the new rendering.
- No model, migration, URL or API change. No respondent-facing surface is touched.
- Behind no new env flag: this restores behaviour that the V2 flag was supposed to preserve.
  Rollback is the template diff.
