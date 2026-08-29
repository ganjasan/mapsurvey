# Responses v2 — full refactor of the Responses tab

## Why

Two UX audits (2026-08-27, in this folder) found the Responses tab optimized for the wrong job on
every form factor: the desktop default is an admin grid whose answer columns sit off-screen while
"how is my survey doing" has no screen at all; Data and Performance show contradictory KPIs
(65/98% vs 1/0%) under one heading; the product's best feature — linked cross-filtering — is
invisible; and on phones (which creators actively use for monitoring) the table is unusable and
navigation is quadruplicated. Mobile monitoring is real traffic today, and Responses is the screen
creators return to daily — it should answer their question in one glance.

## What Changes

- **Flat pane set** `Overview · Map · Responses · Charts · Performance` replaces the current three
  stacked navigation axes (Data/Performance × Table/Map/Charts pane tabs × split-pane controls).
- **New Overview pane, the default on every form factor**: KPI strip with daily deltas, map
  thumbnail, response trend, per-question mini-charts, needs-review and latest-responses feeds.
- **Responses pane (the table), re-defaulted**: per-survey sequence numbers, Started/Duration/
  status-chip/answer columns first; Issues/Trash/Complete become toolbar filter chips (the
  Violations sidebar is removed); row click opens a **detail drawer** (desktop: side panel with
  prev/next; tablet: overlay; phone: full-screen card list instead of the table).
- **Global filter pills**: active FilterManager filters render as a persistent pills row visible on
  every pane; charts advertise clickability.
- **Performance reconciled**: joins the flat pane set; its KPIs are explicitly labeled as
  tracked-visit metrics so they no longer read as contradicting the response counts.
- **Split view becomes an explicit labeled control** (desktop-only) instead of unlabeled icons;
  panes inside a split lose their duplicated tab rows.
- **Mobile layout** (<768px): bottom bar Overview/Map/Responses/Perf; Charts content lives inside
  Overview; full-screen map with sheet-based feature details; no whole-page horizontal scroll.
- **Kill switch**: `RESPONSES_V2` env var (default ON after review) serves the old template when
  off — the rollback story, per merge-reaches-prod-in-minutes policy.
- What does NOT change: FilterManager/SelectionManager engines, analytics endpoints and partials
  (table HTMX endpoint, geo map data, charts data), export, version scoping semantics.

## Capabilities

### New Capabilities
- `responses-overview`: the default Overview pane — KPI strip with deltas, needs-review feed,
  latest responses, map thumbnail, trend; identical data on all form factors.
- `responses-navigation`: the flat pane set, its per-form-factor collapse (5 panes + split on
  desktop, 5 on tablet, 4 with bottom bar on phone), and the `RESPONSES_V2` kill switch.
- `responses-detail-drawer`: row/feature → detail surface with status controls and prev/next,
  replacing the Session Details modal; drawer/overlay/full-screen per form factor.

### Modified Capabilities
- `analytics-data-workspace`: split panes become an explicit opt-in mode without duplicated tab
  rows; the height-preservation and fullscreen-degradation requirements are restated against the
  new pane structure; global filter pills row; table default columns and chip filters.
  (The Performance-KPI "tracked visits" labeling, audit finding D2, is specified in the new
  `responses-navigation` capability — it is a pane-presentation rule, and `creator-funnel-events`
  covers only event capture.)

## Impact

- **Templates**: `survey/templates/editor/analytics_dashboard.html` (major restructure), partials
  `analytics_table.html`, `analytics_overview.html`, `analytics_session_detail.html`,
  `partials/_mobile_nav.html` (Responses item set), new `analytics_overview_pane.html`.
- **Static**: `survey/assets/css/editor-mobile.css`, new `css/responses-v2.css`, split-pane and
  pane-switch JS inside the dashboard template; SelectionManager/FilterManager untouched in
  behavior, re-bound to new DOM.
- **Backend**: `editor_views.py` analytics view gains Overview aggregates (daily deltas, latest
  responses feed); `settings.py` gains `RESPONSES_V2`; no model or migration changes.
- **Tests**: `survey/tests.py` — new template/DOM assertions for pane structure, kill-switch
  round-trip, drawer endpoint reuse of `analytics_session_detail`; existing analytics tests
  updated where they assert on the old Data/Performance markup.
- **Docs**: CLAUDE.md mobile section (the Responses vocabulary changes from
  Table/Map/Charts/Perf to Overview/Map/Responses/Perf).
