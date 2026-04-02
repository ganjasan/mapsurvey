# Cross-filtering / cross-highlighting in analytics dashboard

**Type**: feature
**Priority**: medium
**Area**: frontend
**Epic**: survey-analytics
**Created**: 2026-04-02
**Depends on**: [Survey analytics dashboard](feature-survey-analytics-dashboard.md)

## Description

When a user clicks on a chart element (e.g., "Plutôt insatisfait" bar in a choice distribution), highlight the corresponding sessions across all other dashboard components: daily chart shows those sessions' days highlighted, geo map highlights their points, other question stats show those respondents' answers. This is the "cross-highlighting" pattern used in Power BI, Tableau, and similar BI tools.

## Research Notes

Two interaction patterns exist:
- **Cross-highlighting**: clicked subset is emphasized, rest is dimmed but still visible. Better for part-to-whole comparisons. Recommended for our case.
- **Cross-filtering**: clicked subset replaces all data in other charts. Better for drill-down analysis.

### Implementation Options

**Option A: Chart.js onClick + manual coordination**
- Use `getElementsAtEventForMode()` to detect clicks
- Maintain shared state (selected session IDs) in JS
- Update other Chart.js instances with highlighted datasets + call `.update()`
- Update Leaflet map by styling selected vs non-selected features
- Pros: no new dependencies, works with existing Chart.js setup
- Cons: all coordination logic is manual, complex with many chart types

**Option B: Crossfilter.js + dc.js**
- Replace Chart.js with dc.js (D3-based charting with native crossfilter support)
- All charts bind to a shared crossfilter dataset
- Click on one chart auto-filters all others via Chart Registry
- Leaflet integration exists: github.com/austinlyons/dcjs-leaflet-untappd
- Pros: built-in cross-filter behavior, handles complex interactions automatically
- Cons: replaces Chart.js (migration effort), dc.js has steeper learning curve, larger bundle

**Option C: Hybrid — Chart.js for rendering, crossfilter.js for data**
- Use crossfilter.js for data management and filtering logic
- Keep Chart.js for rendering (familiar, already in use)
- Manual bridge between crossfilter dimensions and Chart.js datasets
- Pros: best of both worlds — efficient filtering + familiar rendering
- Cons: requires custom bridge code

### UX Best Practices (from research)
- Show hint text: "Click on chart elements to filter" — users don't discover this on their own
- Provide "Clear filter" button when any filter is active
- Cross-highlighting (dim non-matching) is better than cross-filtering (hide non-matching) for survey data — context matters
- Consider performance with large datasets — crossfilter.js is specifically optimized for this
- Primary filters (date range, section) should be conventional dropdowns, not chart clicks

## Sources
- [Power BI: Filters and highlighting](https://learn.microsoft.com/en-us/power-bi/create-reports/power-bi-reports-filters-and-highlighting)
- [Metabase: Cross-filtering tutorial](https://www.metabase.com/learn/metabase-basics/querying-and-dashboards/dashboards/cross-filtering)
- [dc.js + Crossfilter tutorial](https://medium.com/@louisn_23157/interactive-dashboard-crossfilter-dcjs-tutorial-7f3a3ea584c2)
- [Chart.dc.js — Chart.js + Crossfilter integration](https://github.com/nsubordin81/Chart.dc.js)
- [Crossfilter.js](https://square.github.io/crossfilter/)
- [Chart.js Interactions API](https://www.chartjs.org/docs/latest/configuration/interactions.html)
- [Dashboard UX Best Practices 2026](https://www.designrush.com/agency/ui-ux-design/dashboard/trends/dashboard-ux)
- [Highcharts Crossfilter Demo](https://www.highcharts.com/demo/dashboards/crossfilter)

## Notes

- Evaluate Option A first (minimal change) — if coordination becomes too complex, migrate to Option C
- Consider this as Phase 1.5 — after MVP dashboard is validated with bisqunours but before Phase 2 event tracking
