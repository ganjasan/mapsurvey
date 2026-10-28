# Proposal: performance-section-funnel

## Why

The Section Funnel on the survey Performance tab counts *events*, not sessions. A respondent who
refreshes or navigates back adds another `section_view`, so every section reads "26 views → 24
submits −8%" with a nearly full green bar, and the Chart.js bar chart below repeats the same
numbers. Nothing on the tab answers the question a creator actually has: *how many respondents
reached each step, and where do they leave?* The owner compared it to a PostHog funnel
(step columns as % of entrants, hatched drop-off, per-step "reached / dropped" lines) and asked for
that shape.

## What changes

- `PerformanceAnalyticsService.get_funnel()` counts **distinct sessions** per section (reached =
  viewed, completed = submitted) and adds `reached_pct` (of sessions started) and
  `dropped`/`dropped_pct` (vs. the previous step's reached count). Raw `views`/`submits` event
  counts stay in the payload for the tooltip.
- The Section Funnel partial is redrawn as a PostHog-style step funnel: one column per section,
  bar height = `reached_pct`, hatched remainder, and under each column the step number, title,
  "N reached (x%)" and "↘ M dropped (y%)". Pure CSS/HTML, no Chart.js; below 768px the
  steps stack vertically with a horizontal bar each (no horizontal scrolling). Each step also
  shows the median time on the section (from `page_leave`, same source as the Time on Section table). The per-section progress bars and the Chart.js bar chart are
  removed.
- Sessions Started is the funnel entry (100%). A section reached by more sessions than the
  previous one (conditional branches, rearranged sections) shows 0 dropped, never a negative.

## Out of scope

- Changing what events are emitted.
