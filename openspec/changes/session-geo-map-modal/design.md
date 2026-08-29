## Context

Responses V2 (`RESPONSES_V2`, archived change `responses-v2-refactor`) replaced the Session
Details modal with a detail surface — a drawer at ≥1200px, an overlay panel at 768–1199px, a
full-screen view below 768px (spec `responses-detail-drawer`). The surface renders from the
unchanged `analytics_session_detail` endpoint into `#rv2-drawer-body` via
`htmx.ajax(..., {target: '#rv2-drawer-body'})` (`analytics_dashboard_v2.html:1016`).

The partial it renders still carries the V1 mini-map, and that mini-map is dead:

```js
var modalEl = document.getElementById('sessionDetailModal');   // null in v2
if ($(modalEl).hasClass('show')) { setTimeout(initMiniMap, 50); }
else { $('#sessionDetailModal').one('shown.bs.modal', initMiniMap); }  // empty collection
```

`analytics_dashboard_v2.html` contains no `#sessionDetailModal` (0 occurrences), so neither branch
runs. `{% if has_geo %}` still emits `<div id="session-mini-map" style="height:200px">`, which
renders as blank space under Notes. The V1 dashboard still has the modal, so the same partial must
keep working on both paths while `RESPONSES_V2` remains a kill switch.

What the creator sees today for a geo answer is the string `point feature`, produced by
`SurveyAnalyticsService.format_session_answers` (`analytics.py:892-894`). The attribute table uses
a different formatter (`analytics.py:1265-1279`) that already yields `39.71, −77.48` and
`3 vertices`.

Two facts shape the design:

- `format_session_answers` builds `geo_features` whose properties are `{question, type,
  attributes}` — there is **no per-object identifier**, so nothing today can tie the drawer row
  for "point feature 2" to its feature on a map.
- The numbering that distinguishes sibling objects (`geo_object_counts`) is computed in that same
  loop and currently only reaches the row's display string.

## Goals / Non-Goals

**Goals:**

- A creator reading one response can see all of its geo objects on a full-size map, in one action.
- Row ↔ object correspondence is unambiguous when a question has several objects.
- The drawer preview stops being a blank box.
- The failure mode that caused this (markup moved, initialiser left behind) becomes a test failure.

**Non-Goals:**

- Filtering the main Map pane to a single session; that is a separate change.
- Editing geometry from the modal — the modal is read-only.
- Any respondent-facing change.
- Reworking the Map pane's own popups or legend.

## Decisions

**1. Initialise the preview from the partial itself when no modal exists.**
The partial branches on whether `#sessionDetailModal` is present: with it, the V1 timing
(`shown.bs.modal`) is kept; without it, it calls the initialiser directly, since HTMX re-executes
inline `<script>` on every swap and the drawer is already visible when the swap lands.
`initMiniMap` is also published as `window.initSessionMiniMap` so a host surface can drive it.
*Alternative considered, and initially chosen in this design*: binding `htmx:afterSwap` for
`#rv2-drawer-body` in the host page, next to the handlers already at lines 473 and 1044. Rejected
during implementation — it makes the preview depend on a host page remembering to register a
listener, which is the exact coupling that broke here. The template that owns the container
should own its initialisation.

**2. One Leaflet setup for both surfaces.**
V1 keeps its `shown.bs.modal` binding, V2 initialises inline, and both run the same `initMiniMap`,
which disposes any previous instance first. Rationale: preserves the kill-switch rollback story
without a second copy of the setup.

**3. Add a stable `object_id` (the geo `Answer.pk`) and `label` to each feature's properties.**
`format_session_answers` already computes both the numbering and the feature; emitting
`{question, type, attributes, object_id, label}` lets the drawer row carry
`data-geo-object-id` and the modal highlight/zoom exactly one object, and lets the popup title
read the same "point feature 2" the row shows. Rationale: without an id, row→object matching
would rely on question name + ordinal reconstructed on the client, which breaks the moment
ordering or filtering changes.
*Alternative considered*: index within the feature collection — rejected, it is positional and
silently wrong after any reordering.

**4. Row display value comes from the existing attribute-table formatter.**
Reuse the `39.71, −77.48` / `3 vertices` formatting (`analytics.py:1265-1279`) for the drawer row
instead of `point feature`, keeping `label` ("point feature 2") for the popup title and for
disambiguating siblings. Rationale: one formatter, and the drawer stops disagreeing with the
table for the same answer.

**5. One modal, opened from both entry points.**
The geo row and the preview both call the same opener with an optional object id: from the row,
the modal zooms to that object and opens its popup; from the preview, it fits all objects. The
modal lives in `analytics_dashboard_v2.html` next to `validationSettingsModal` (line 181) and
draws from the same payload already in the drawer — **no new endpoint and no extra request**
(verified: opening it fires zero further `/analytics/` requests).

**5a. The modal builds its own tile layer instead of including `basemap_layers.html`.**
That include writes `window._basemapLayers` and `window._layersControl` — state owned by the Map
pane. Including it a second time would overwrite the pane's layer switcher, so the modal
constructs a single tile layer from `MAPBOX_URL` / `MAPBOX_ACCESS_TOKEN` directly. Cost: the modal
has no basemap switcher. Accepted — it is a read-only look at one response.

**5b. The payload reaches the page through `json_script`, not interpolation.**
`{{ geo_json }}` inside a `<script>` block is HTML-escaped by Django and the JSON no longer
parses; `|safe` is not an option, because these properties carry respondent text. `json_script`
resolves both: it escapes what must be escaped and still emits valid JSON. The view therefore
passes the collection as an object alongside the existing `geo_json` string the V1 mini-map reads
via `escapejs`.

**6. Colour and legend follow the Map pane's convention** (colour per question, popup listing
sub-answers), so a creator does not learn two visual languages for the same data. The sub-answer
values come from the `attributes` payload that `responses-geo-subanswers` already guarantees, and
stay autoescaped — the JSON block must not be marked safe.

**7. The regression guard asserts the contract, not the pixels.**
A test that the dashboard template (per `RESPONSES_V2` state) contains the container id the
partial's initialiser binds to. Rationale: the original break was invisible to Django tests
because it was pure client-side wiring; a template-level contract test is the cheapest thing that
would have caught it. This matches the repo's existing lesson that a dead control passes every
Django test.

## Risks / Trade-offs

- **[The dead mini-map may not be the only V1→V2 casualty]** → while implementing, grep the
  partials rendered into `#rv2-drawer-body` for other `#sessionDetailModal` / `.modal(` references
  and report what is found, rather than fixing only the one the owner noticed.
- **[Leaflet in a hidden container sizes to 0]** → the modal must `invalidateSize()` after it is
  shown, and the preview must initialise only once the drawer is visible; this is the classic
  cause of a grey half-rendered map.
- **[Repeated swaps leak map instances]** → the existing code already nulls `window._sessionMiniMap`
  before re-init; the modal needs the same discipline on close, or prev/next triage accumulates
  detached Leaflet instances in a long editing session.
- **[Sessions with many objects]** → a session is one respondent's answers, so the object count is
  bounded by the survey's geo questions; no clustering needed. If a single question accepts
  multi-feature input (`geo-multi-feature-input`), the count is still per-respondent and small.
- **[Adding `object_id` to feature properties]** → the same `geo_features` shape feeds the drawer
  only (the Map pane builds its own payload), but this must be verified, not assumed, since
  `responses-geo-subanswers` pins the existing property names and requires they be preserved.
- **[Trade-off: no isolate-on-main-map]** → the owner asked for a modal, which keeps the Map
  pane's filter state untouched; the cost is that the modal cannot show the session in the
  context of all other responses. Accepted for this change.

## Migration Plan

Template- and formatter-level change; no model, migration, URL or API change. Ships on the
existing `RESPONSES_V2` switch — with the flag off, the V1 modal path behaves exactly as before.
Rollback is reverting the diff; there is no persisted state to unwind.

Because merges reach production within minutes and there is no staging gate, the failure modes
this change *introduces* (map in a hidden container, leaked instances across prev/next, popup
escaping) must be exercised in a browser before merge, not only in tests.

## Resolved during implementation

- **Who consumes `geo_features`?** Only `analytics_session_detail` (`analytics_views.py:199`) and
  tests. The Map pane builds its own collection at `analytics_views.py:135`, so the added
  properties reach nothing else.
- **Breakpoints.** The modal was driven at 1000×800 and 420×860: it opens, stays inside the
  viewport (798×560 and 402×602 map areas), and loads tiles at both. No mobile-specific treatment
  was needed.
- **Implementation checkout.** Done in a fresh worktree from `origin/master`
  (`Mapsurvey-session-geo-map`, `PORT_OFFSET=240`).

## Findings outside this change's scope

Surveying the V1→V2 leftovers (task 1.1) turned up one more casualty, reported rather than fixed
so this change stays scoped:

- **`restoreSession` was never re-pointed for V2.** `analytics_dashboard_v2.html` overrides
  `loadSessionDetail`, `trashSession` and `hardDeleteSession`, but not `restoreSession`. Restoring
  a trashed response therefore still runs the shared engine's version, whose success callback is
  `$('#sessionDetailModal').modal('hide')` — a no-op in V2, so the detail surface stays open on a
  response that is no longer in the trash list. The same dead call sits in the partial's own
  Restore/Delete buttons (`analytics_session_detail.html:18,21`).

Also fixed in passing, because the new row value depends on it: `_format_cell` read
`polygon.exterior`, which GEOS polygons do not expose (`exterior_ring` is the accessor), and a
blanket `except Exception` turned that AttributeError into the literal string "polygon". Every
polygon in the attribute table has therefore been showing its type instead of its vertex count
since the formatter was written.
