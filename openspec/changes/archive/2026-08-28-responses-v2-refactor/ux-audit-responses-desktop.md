# UX Audit — Responses tab, desktop (1440×900)

Date: 2026-08-27 · Survey: citypulse (65 sessions, 129 geo features) · Dev stand :8020, fresh profile (localStorage cleared).

Companion to `ux-audit-responses-mobile.md`. Goal: baseline for a full Responses refactor; the V1 mobile concept ("monitoring feed") is the candidate direction to port back.

Screens captured: `d-table.png`, `d-map.png`, `d-charts.png`, `d-split.png`, `d-session.png`, `d-perf.png`.

---

## D1 — The default screen answers the wrong question (major)
First paint is the **Table**: an admin grid whose first eight columns are checkbox, eye/trash, raw DB id (#1464), a per-row Status `<select>`, Issues, Tags, Start time, Language, Version. The actual survey **answers** begin at column 9 and sit mostly off-screen right. A creator opening Responses wants "how is my survey doing" — that answer lives in Charts, one hidden tab away, and even there the daily trend is below the fold. The mobile finding F5 exists on desktop too; desktop just hides it behind more chrome.

## D2 — Two contradictory sets of KPIs in one tab (major, trust-breaking)
Data → Charts says **65 sessions / 64 completed / 98%**. Performance says **1 session started / 0 completed / 0%** (it counts only `SurveyEvent`-tracked sessions). Both live under the same "Responses" heading with no explanation of the different denominators. A creator who sees 0% completion next to 98% concludes the product can't count. Either reconcile the numbers, label them explicitly ("of tracked visits"), or merge Performance into the same scope.

## D3 — Navigation is three stacked axes for six destinations (major)
Data/Performance (axis 1) × Table/Map/Charts pane tabs (axis 2) × split-pane controls (axis 3). Performance is a sibling of Table/Map/Charts in every meaningful sense — one flat set (Overview / Map / Table / Charts / Performance) removes an entire navigation level. The current arrangement also duplicates the whole tab row into **each** split pane.

## D4 — The table is a data-cleaning tool wearing a monitoring tab's clothes (major)
- Per-row `<select>` for status renders 50 dropdowns per page — visual noise for an action used on exceptions, not on every row.
- Raw session pks (#1464) carry zero meaning; a per-survey sequence (#1…#65) plus start time is what humans use.
- Language ("en" × 65) and Version ("v1" × 65) occupy prime columns while answers hide off-screen. No frozen answer column by default (the `col-frozen` machinery exists, unused).
- The eye icon opens details; row click does nothing — the biggest click target is inert.
- "Trash" is a *view toggle* styled as a destructive-looking action button; the gear hiding Validation Settings is unlabeled.

## D5 — Split panes: high machinery cost, near-zero discoverability (moderate)
The split-right/split-down/close affordances are 10px gray icons with no labels; a first-time user cannot know the IDE layout exists (SelectionManager memory: this is an owner power feature — keep it, but it shouldn't tax everyone). Costs it imposes on everyone: a duplicated Table/Map/Charts tab row per pane, a second toolbar row when the table pane narrows (buttons wrap, `d-split.png`), and a localStorage layout that silently persists with no visible "reset layout".

## D6 — Cross-filtering is the product's best feature and is completely invisible (major)
FilterManager wires chart-segment clicks, map lasso, timeline brush and the table into one linked-views system — the thing desktop GIS users pay for. Nothing advertises it: bars don't show a pointer/hover hint, the filter-pills bar is `display:none` until first use, and the map's rectangle/lasso tools are unlabeled 30px icons on the map's right edge. The selection bar (Hide / Keep only / Invert) uses one vocabulary in Map/Charts panels while the table uses another (checkboxes + bulk actions) for the same concept.

## D7 — Redundant controls per panel (minor)
- Response Timeline offers **three** ways to set the same range: two datetime pickers in the header, two "Range:" inputs under the chart, and draggable purple brush handles — pick one (brush) and derive the rest.
- Three coexisting "make it bigger" mechanisms: browser `requestFullscreen` per panel, the Charts focus mode (⛶ per question card), and split-pane maximization. Each behaves differently.
- Violations sidebar auto-expands to ~230px to show one checkbox; it is a *filter* presented as a *panel* — as chips on the toolbar ("Issues 1") it costs nothing (the mobile 3b pattern).

## D8 — Session Details modal is a dead end (moderate)
`d-session.png`: timestamp, raw id, Trash button, Tags/Notes. No status control (that lives only in the table dropdown), no prev/next to triage a series, no link to the session's geometry on the map. Moderation therefore means: open modal → close → find next row → open again. The mobile 3d screen (full detail + status chips + map context) is the better pattern and ports back directly.

## D9 — Performance content issues (minor)
Section Funnel renders −100% drop in alarm-red from a 1–2 session sample; below ~20 sessions this is noise presented as catastrophe (k-anonymity thinking from public results applies here too: suppress or soften under a minimum sample). Traffic Sources "Other: 1" — bucket everything until there's signal, or show an empty-state explainer.

## D10 — No liveness (moderate)
Monitoring implies "since last visit": no deltas (+7 today), no new-response indicator, no auto-refresh (charts are 60s-cached for public results; the editor dashboard has nothing). The page is a report, not a monitor.

## What works and must survive the refactor
- The linked-views engine itself (FilterManager/SelectionManager) — refactor is UI, not the model.
- Split panes as an opt-in power layout (owner uses it; SelectionManager refactor memory).
- Column filters, per-column search, hide/freeze machinery in the table.
- Map layer legend with per-question layers, heat settings.
- Version scoping + Download in one place.
- Flagged KPI card highlighting (orange) — the one place where the dashboard already "speaks".

---

# Direction for the refactor (V1 ported to desktop)

One flat pane set, one persistent rail:

```
┌ Survey ▸ Responses ▸ Public results ──────────────── All versions ▾  ⬇ ┐
│ Overview · Map · Responses · Charts · Performance          [filters ◈] │
├────────────────────────────────────────────────────────────────────────┤
│ KPI strip (always visible, all panes): 65 (+7) · 98% · 4:12 · 129 (+11)│
├────────────────────────────────────────────────────────────────────────┤
│                         active pane content                            │
```

- **Overview** = desktop Pulse: KPI with deltas, map thumbnail, trend, per-question mini-charts, latest responses. Becomes the default pane (D1).
- **Responses** = the table, re-defaulted: sequence numbers, Start time + Duration + first answers first; status as a chip that opens on click, not a permanent select; Issues/Trash as toolbar chips (D4, D7); row click opens a right-side **detail drawer** (not a modal) with status chips, answers, mini-map, prev/next (D8).
- **Performance** joins the flat set; its KPIs get explicit "tracked visits" labels or are reconciled (D2, D3).
- **Filter bar is global and always visible when active** — the mobile 4c pattern: one pills row above the KPI strip, shared by all panes (D6). Charts get hover cursors + a one-time hint ("click a bar to filter everything").
- **Split view stays** but as an explicit "Split view" button in the pane row (label, not icon), and panes inside a split show only content — the single global pane row drives what goes where (D5).
- **Liveness**: daily delta chips on KPIs; a lightweight "N new since you opened" toast with refresh (D10).

Kill switch: `RESPONSES_V2` env var serving the old template, per merge-to-prod-in-minutes policy.
