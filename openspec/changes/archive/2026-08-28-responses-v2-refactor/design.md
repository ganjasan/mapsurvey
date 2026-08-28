# Design — Responses v2

## Context

The Responses tab (`analytics_dashboard.html`, ~2600 lines) is one template carrying three
navigation systems, a split-pane tree engine, FilterManager/SelectionManager linked views, the
attribute table (HTMX partial), the geo map, charts, and the Performance sub-page. Two audits
(`ux-audit-responses-desktop.md`, `ux-audit-responses-mobile.md`) and three approved mockups
(`responses-v2-all.mockup.html` — desktop/tablet/mobile; `responses-v2-mobile-full.mockup.html` —
15 mobile screens) define the target. The `fix-analytics-map-collapse` change already hardened the
height chain; its spec (`analytics-data-workspace`) is the one we extend.

Constraints: merge reaches prod in minutes (no staging) — everything ships behind `RESPONSES_V2`;
the owner uses split panes and the linked-views engine daily — engines must not regress; the
respondent side is untouched; no model/migration changes (parallel-worktree migration policy).

## Goals / Non-Goals

**Goals**
- Overview pane answering "how is my survey doing" as the default on all form factors.
- One flat pane vocabulary (Overview/Map/Responses/Charts/Performance) across desktop ≥1200,
  tablet 768–1199, phone <768.
- Detail drawer replacing the Session Details modal, with prev/next triage.
- Global, always-visible-when-active filter pills; discoverable chart/map filtering.
- Honest Performance numbers (explicit "tracked visits" labeling).

**Non-Goals**
- No changes to FilterManager/SelectionManager semantics, analytics endpoints, export, or version
  scoping logic.
- No new aggregation backend beyond Overview deltas/feeds (reuse existing queryset helpers).
- No table virtualization or server-side changes to `analytics_table` beyond column defaults.
- The in-flight SelectionManager refactor is not folded in; v2 binds to whatever selection API
  exists at implementation time.

## Decisions

**D-A. One template, three media tiers — not separate mobile templates.**
The pane row, KPI strip and pane containers are one DOM; CSS grid/media queries collapse them.
Alternative (separate mobile template) rejected: double maintenance and the exact drift the
mobile audit documented.

**D-B. `RESPONSES_V2` kill switch at the view level.**
The analytics view renders `analytics_dashboard_v2.html` when on, the legacy template when off.
A separate template file (not in-template conditionals) keeps the legacy path byte-identical and
lets us delete it in one commit later. Legacy template stays untouched during the change.

**D-C. Overview aggregates are computed server-side in the existing view.**
Daily deltas (`+N today`), latest-5 responses, needs-review count come from querysets already
used by the table/overview partials — one extra cheap query each, same version-scope filter.
Alternative (client-side from table JSON) rejected: Overview must render before any panel JS.

**D-D. Drawer reuses `analytics_session_detail` HTMX endpoint.**
The modal body partial becomes the drawer body; prev/next navigates the current filtered/sorted
id list, which the table JS already holds client-side. No new endpoint.

**D-E. Split view: a simple two-pane mode, not the legacy tree.**
(Revised during implementation.) The legacy `_splitTree` engine stays legacy-only; v2 ships a
flat two-pane split: the active pane on the left, a companion on the right, driven entirely by
the pane row (clicking the companion's tab swaps sides). No nested splits, no per-pane tab bars.
Rationale: the tree's cost — duplicated tab rows, drag dividers, layout serialization — bought
depth nobody discovered (audit D5); two panes cover the owner's real use (map + charts / table).
Split state persists in localStorage keyed by survey, with a visible "Reset layout" control.

**D-F. Pane switching is URL-hash-addressable** (`#overview`, `#map`, …) so Share/Perf deep links
(`#traffic-sources`) keep working and the mobile bottom bar and desktop pane row share one
router function.

**D-G. Filter pills render from FilterManager state via a registered component**, exactly like
existing chart/table listeners — the pills bar is just one more subscriber; clearing a pill calls
the existing clear APIs.

**D-H. Naming: "Pulse" is dropped; the pane is "Overview" everywhere** (mobile bar label
included) — one vocabulary across form factors and docs.

## Risks / Trade-offs

- [Template rewrite regresses a hidden behavior of the 2600-line file] → legacy template kept
  verbatim behind the switch; DOM-level tests for every pane; owner runs both side by side on the
  dev stand before default-ON.
- [Leaflet in a resized/hidden pane collapses again] → reuse the invalidateSize discipline and
  the `analytics-data-workspace` height scenarios as regression tests; the guard test suite runs
  on the new template too.
- [Drawer prev/next diverges from filtered order after live refresh] → prev/next iterates the id
  list snapshot taken at open; refresh closes the snapshot with a "list changed" hint.
- [Split-view users lose muscle memory] → split persists, reset is visible, and the legacy
  switch stays for one release cycle.
- [Overview queries slow on large surveys] → each aggregate is a single indexed-filter query;
  measured on the loadtest seed survey before default-ON.

## Migration Plan

1. Ship v2 template + `RESPONSES_V2` default **OFF**; verify on Render PR preview.
2. Owner review on dev stand (both templates), then flip default ON in a follow-up commit.
3. Legacy template removal is a separate future change after ≥2 weeks of quiet.
Rollback at any point = env var off, no data implications.

## Open Questions

- Overview "Needs review" feed: violations only, or also `on_hold` sessions? (Start: violations
  only — matches the badge count.)
- Tablet drawer overlay width (mockup: 52%) — fixed % vs clamp(320px, 45%, 560px); decide in CSS
  review.
- Does the pane row expose Charts on phones later (currently folded into Overview) if question
  count is large? Deferred; Overview links "Charts ›" per question card.
