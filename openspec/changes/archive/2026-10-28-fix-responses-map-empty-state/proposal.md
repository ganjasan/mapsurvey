## Why

The Responses → Map pane shows "No geo questions in this survey" whenever the map has no
features — including surveys that *do* have point/line/polygon questions but no answers yet.
A creator who just published reads it as "my map question is broken" (owner report, 2026-09-05).

## What Changes

- The empty map pane tells the two stories apart: with geo questions and no answers it says
  "No map answers yet" and explains the map fills as responses arrive; without any geo question
  it keeps "No geo questions in this survey" with the "Add a map question" action.
- Both dashboards (v2 and legacy) get the split; the view passes `has_geo_questions`.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `responses-overview`: adds a requirement for the Map pane empty state.

## Impact

`survey/analytics_views.py` (one context key), `analytics_dashboard_v2.html`,
`analytics_dashboard.html`, `ResponsesMapEmptyStateTest`.
