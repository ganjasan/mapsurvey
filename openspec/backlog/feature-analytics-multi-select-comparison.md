# Multi-color selection sets for analytics comparison

**Type**: feature
**Priority**: medium
**Area**: frontend
**Created**: 2026-04-02

## Description

Allow creating multiple named selection sets (each with a distinct color) in the analytics dashboard. Currently only one cross-filter selection is possible. With this feature, a user could create e.g. a blue selection ("Group A") and a red selection ("Group B"), each filtering by different answer criteria, and then visually compare how these groups differ across all other questions. Charts would overlay or split by color to show the comparison.

## Example Use Cases

- **Priority comparison**: Blue = respondents who prioritized "parks", Red = respondents who prioritized "roads" → compare demographics and other preferences
- **Geographic comparison**: Blue = responses from northern neighborhoods, Red = southern → compare priorities by area
- **Demographic comparison**: Blue = residents 5+ years, Red = newer residents → compare vision for the community
- **Event vs online**: Blue = kiosk responses at farmers market, Red = online responses → check if engagement method biases results

## UX Concept

1. Current single-selection cross-filter becomes "Selection A" (default blue)
2. User clicks "+ Add comparison group" → gets "Selection B" (red)
3. Each selection group has its own color chip and can be independently filtered by clicking bars/segments/map areas
4. Charts show overlaid bars, split segments, or side-by-side panels colored by group
5. Response count shown per group: "Blue: 84 responses, Red: 62 responses"
6. Up to 3-4 comparison groups (beyond that, visual clarity degrades)

## Technical Considerations

- Extends the existing cross-filtering mechanism (backlog #33)
- Each selection set is a separate filter predicate applied to the same dataset
- Chart rendering needs to support grouped/stacked bars and multi-series overlays
- Color palette should be colorblind-friendly (blue/orange/green/purple rather than red/green)

## Notes

- Builds on top of cross-filtering (backlog #29 / #33) — should be implemented after basic cross-filtering is stable
- Related to survey-analytics epic but distinct enough to warrant its own item
