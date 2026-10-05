## Why

The Responses Map pane can show where POINT answers pile up (leaflet.heat) and, since the spray
question type (#238), where spray clouds agree (`L.SprayAgreementLayer`). LINE and POLYGON
answers get neither: they are drawn as translucent shapes (`weight: 2, fillOpacity: 0.2`) whose
overlap is whatever alpha stacking produces — coloured by question, not by count, saturated past
four or five shapes, invisible for two-pixel lines. "Where do respondents agree?" is the reason a
creator asks "draw the area you consider the centre" or "draw your route", and the product has no
answer for it. GitHub #242, the first item of the coverage-analytics epic (#245).

## What Changes

- A LineString / Polygon (and Multi*) answer layer on the Responses Map pane gains a **Coverage**
  action in its layer menu, next to where Point layers have *Create Heatmap*. It creates a
  **coverage surface**: for every geographic cell, the share of respondents in scope whose shape
  covers it — a polygon covers the cells inside it, a line covers the cells within a corridor of W
  metres around it. Each respondent counts once per cell whatever the size or number of their
  shapes.
- The surface is `L.SprayAgreementLayer` generalised: the same world-anchored metre cells, the same
  `grid` rendering (crisp cells in the layer's colour, opacity by share), the same session-filter
  hookup. Spray clouds, polygons and lines become three inputs of one layer class; the spray
  rendering does not change.
- The surface is a slot of the `LayerManager` like a heatmap: listed in the Layers panel under its
  source with a swatch, rename, opacity, a settings popover (corridor width for line sources, cell
  size) and a remove button; order/visibility/opacity persist in the per-survey browser prefs like
  every other slot. A legend line reads "1 … N respondents", never "hot".
- No model, query, export or public-results change. Exact counts for export and the results page
  are #243; the agreement contour is #244.

## Capabilities

### New Capabilities
- `responses-coverage-surface`: the Responses Map pane's coverage surface for line and polygon
  answers — what it counts, how it is created, filtered, styled and removed.

### Modified Capabilities
<!-- none: spraycan-density-views (delta in the active change spraycan-question-type) keeps every
     requirement; this change only widens the inputs of the layer class it names. -->

## Impact

- `survey/assets/js/spray_layer.js`: `L.SprayAgreementLayer` accepts members whose coverage is a
  MultiPoint (today), a polygon or a line; rasterises shapes into its cell grid.
- `survey/templates/editor/partials/analytics_geo_map.html`: `LayerManager` slot type `coverage`,
  layer menu entry for line/polygon sources, panel row, settings popover, prefs.
- `survey/tests.py`: template-contract tests in the style of `AnalyticsHeatLayerGuardTest`.
- Changelog entry `survey/changelog/2026-10-xx-coverage-surface.html`.
- Run `collectstatic` after editing `survey/assets/`.
