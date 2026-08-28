# Tasks — responses-v2-refactor

## 1. Skeleton and kill switch

- [x] 1.1 Add `RESPONSES_V2` setting (env-driven, default off for now) and branch the analytics
      view to render `analytics_dashboard_v2.html` when on; legacy template untouched
- [x] 1.2 Create `analytics_dashboard_v2.html` extending `editor_base.html`: top bar (version
      scope + Download), flat pane row, empty pane containers, hash router (`#overview` …)
      shared by pane row and (later) mobile bottom bar
- [x] 1.3 New `css/responses-v2.css` with the three media tiers (≥1200 / 768–1199 / <768) and
      the pane-row/KPI-strip/pills layout primitives; run collectstatic
- [x] 1.4 Guard test: `RESPONSES_V2` off serves the legacy markup byte-identically (template name
      assertion + smoke of old nav ids)

## 2. Overview pane

- [x] 2.1 View aggregates for Overview: daily deltas (responses, geo features), latest-5 feed,
      needs-review list, median time — all under the active version scope
- [x] 2.2 `partials/analytics_overview_pane.html`: KPI strip (with flagged card), map thumbnail
      (view-only Leaflet, omitted when no geo questions), 7-day trend, question mini-charts,
      needs-review + latest feeds
- [x] 2.3 Empty state (zero sessions): "No responses yet" with Share + Preview actions, no
      zero-KPI cards
- [x] 2.4 Tests: default pane is Overview; deltas math (day boundary); version-scope narrowing;
      empty-state branch; no-geo branch

## 3. Pane routing and Performance honesty

- [x] 3.1 Wire Map/Charts/Performance content into the v2 pane containers (move, don't rewrite:
      existing partials render inside new panes); remove Data/Performance row and per-pane tab
      bars from the v2 path
- [x] 3.2 Violations badge on the Responses pane item
- [x] 3.3 Performance: "tracked visits" labels on session KPIs; small-sample (<20) funnel notice
      instead of drop-rate alarms
- [x] 3.4 Preserve `#traffic-sources` deep link through the hash router
- [x] 3.5 Tests: hash routing per pane; badge; tracked-visit label; small-sample funnel; deep link

## 4. Responses pane (table v2)

- [x] 4.1 Table defaults: per-survey sequence number, Started/Duration/Status-chip first, answers
      next; language+version hidden by default (available in Columns control)
- [x] 4.2 Status chip + on-demand control replaces per-row `<select>`; wire to existing
      set-status endpoint
- [x] 4.3 Toolbar chips all/complete/issues/trash with counts replace the Violations sidebar and
      the Trash button; issues chip == old sidebar filtering
- [x] 4.6 Issues chip opens a per-type multi-select menu (errors/warnings groups, counts, clear) —
      the first cut lost individual violation selection (owner review)
- [x] 4.7 Free-text search across all columns in the toolbar (`q` param), composing with chips and
      column filters; focus/caret survive the HTMX swap
- [x] 4.4 Row activation opens the detail surface (kill the eye-icon column); keep checkbox
      column and bulk bar
- [x] 4.5 Tests: default column order; hidden columns; chip filters (incl. trash view); status
      change via chip; row-click handler present in markup

## 5. Detail drawer

- [x] 5.1 Drawer container (desktop side panel / tablet overlay / phone full-screen) fed by the
      existing `analytics_session_detail` HTMX endpoint; row highlight while open
- [x] 5.2 Status control + trash with in-page confirmation inside the drawer; feed/table chips
      update without reload
- [x] 5.3 Prev/next over the opened id-list snapshot; "list changed" hint on live refresh
- [x] 5.4 Retire the Session Details modal in the v2 path (map popups' open-response also
      targets the drawer)
- [x] 5.5 Tests: drawer endpoint reuse; status roundtrip; snapshot navigation; in-page confirm
      (no `window.confirm` in v2 templates)

## 6. Global filter pills and discoverability

- [x] 6.1 Pills row as a FilterManager registered component: pill per active filter, counts
      ("20 of 65 shown"), dismiss + clear-all; hidden when no filters
- [x] 6.2 Pills persist across pane switches (single DOM location above the workspace)
- [x] 6.3 Chart hover cursor + "click a bar to filter" first-time hint; labeled Select/Box/Lasso
      controls on the map
- [x] 6.4 Tests: pill lifecycle (add/dismiss/clear), count text, presence on every pane

## 7. Split view v2 (desktop)

- [x] 7.1 "Split view" labeled control in the pane row driving the existing `_splitTree` engine;
      no per-pane tab bars; pane row indicates both active panes
- [x] 7.2 Persist layout per survey; visible "reset layout"; map `invalidateSize` on split
      enter/leave (spec scenario)
- [x] 7.3 Tests: split enter/close/reset; height retained (extend analytics-data-workspace guard
      tests to v2)
- [x] 7.4 Owner review rounds: QGIS-style map toolbar (Select with shape submenu + Identify),
      QGIS-yellow selection + brown open-response colors, image lightbox, on-map geocoder
      (Nominatim), selection actions merged into the global pills bar, select-all = whole
      filtered set, SelectionManager repaint rewired, seq-sort fix

## 8. Mobile tier

- [x] 8.1 Bottom bar Overview/Map/Responses/Perf bound to the shared hash router; update
      `_mobile_nav.html` responses item set; Charts folded into Overview (question card links)
- [x] 8.2 Responses pane <768px renders the card list (sequence, time, duration, summary, status
      chip) instead of the table; chips row scrolls horizontally inside itself
- [x] 8.3 Map pane <768px: full-height map, feature tap opens the drawer (full-screen), Layers
      as bottom sheet
- [x] 8.4 No document-level horizontal scroll at 390px across all panes (automated check via
      rendered-markup width probes + manual browser pass, per HTML5-validation lesson)
- [x] 8.5 Tests: bottom-bar item set; card-list branch; scrollWidth guard where assertable
- [x] 8.6 Mobile toolbar: always-visible search + "Filters & sort" bottom sheet — Show chips,
      per-type violations, sort by ANY column (field picker + asc/desc), typed per-column
      filters (values/range/date/text) with instant apply (owner review rounds)

## 9. Verification and rollout

- [x] 9.1 Template-comment guard test run over all new/edited templates
- [x] 9.2 Browser pass on dev stand at 390/900/1440 (both switch states), screenshots into the
      change folder
- [x] 9.3 Overview aggregate timing on the loadtest seed survey (before default-ON decision)
- [x] 9.4 Update CLAUDE.md mobile-nav vocabulary (Overview/Map/Responses/Perf); note legacy
      template removal as a future change
- [ ] 9.5 Flip `RESPONSES_V2` default ON (separate commit, after owner review on PR preview)
