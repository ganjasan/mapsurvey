# marker-draw-lifecycle Specification (delta)

## ADDED Requirements

### Requirement: The respondent map is never driven while it has no size
The respondent page SHALL NOT ask Leaflet to move the map while its container has zero size.
Leaflet derives every projection from `map.getSize()`, so a move against a hidden container
unprojects to `LatLng(NaN, NaN)` and throws — once per frame for an animated fly. A `form` section
hides the map through the `survey-form-layout` body class, which makes this reachable in ordinary
use.

#### Scenario: A geolocation result arriving on a form section does not throw
- **WHEN** the geolocation callback returns while the respondent is on a section whose layout hides the map
- **THEN** no map move is attempted and no error is raised

#### Scenario: The deferred location is applied when the map returns
- **WHEN** the respondent moves to a section that shows the map again and that section declares no position of its own
- **THEN** the location that arrived while the map was hidden is applied

#### Scenario: A section's own position wins over a deferred location
- **WHEN** the section that brings the map back declares its own start position
- **THEN** that position is used and the deferred location is dropped, because an explicit section view outranks a stale locate request

#### Scenario: Non-finite coordinates are ignored
- **WHEN** a move is requested with a coordinate or zoom that is not a finite number
- **THEN** the move is skipped rather than passed to Leaflet

#### Scenario: An ordinary section transition still moves the map
- **WHEN** the respondent advances to a visible map section with its own position
- **THEN** the map flies to that position as before
