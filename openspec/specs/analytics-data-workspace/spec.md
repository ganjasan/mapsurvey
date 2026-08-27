# analytics-data-workspace Specification

## Purpose
TBD - created by archiving change fix-analytics-map-collapse. Update Purpose after archive.
## Requirements
### Requirement: Data workspace keeps its height through tab switches
The Responses Data workspace SHALL retain its flex-column layout (and therefore
the full height of its split-pane tree) after any number of Data ↔ Performance
tab switches and after the mobile pane bar selects any panel. The Map panel's
Leaflet container SHALL have a non-zero height whenever the Map panel is shown.

#### Scenario: Map pane on mobile at page load
- **WHEN** the analytics page loads below 768px and the user selects the Map pane
- **THEN** the map container has non-zero height and renders tiles and features

#### Scenario: Desktop Data–Performance round-trip
- **WHEN** the user switches Data → Performance → Data with the Map panel open
- **THEN** the map container keeps a non-zero height and stays rendered

### Requirement: Fullscreen toggles degrade gracefully
Panel fullscreen controls SHALL use the unprefixed Fullscreen API when present,
fall back to the webkit-prefixed API, and do nothing (without throwing) when
neither exists.

#### Scenario: Expand button on iOS Safari
- **WHEN** the user taps a fullscreen toggle in a browser without
  `Element.requestFullscreen`
- **THEN** no exception is thrown

