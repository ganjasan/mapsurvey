## MODIFIED Requirements

### Requirement: Section map position picker
The system SHALL provide a Leaflet map picker for setting a section's start_map_position and start_map_zoom. The picker SHALL open in a wide modal, display a map centered at the section's current position, and allow the user to click to set a new position and adjust zoom. The picker SHALL include the shared place search above the map; choosing a search result SHALL move the map to the place, set the picked position to the result point and the zoom to the result's zoom, uncheck "Inherit position" if it was checked, and update the coordinates label. On viewports of 1024px and wider the map SHALL be at least 480px tall; narrower viewports keep the previous height. The picker's click, zoom, Inherit-checkbox and Save handlers SHALL be registered independently of the place search, so that a picker used without searching is fully operable; no picker template SHALL depend on a Mapbox token or URL declared in an enclosing template scope.

#### Scenario: Set map position by clicking
- **WHEN** the user opens the map picker for a section and clicks on the map at coordinates (30.5, 60.0) with zoom level 14
- **THEN** the section's start_map_position is set to Point(60.0, 30.5) and start_map_zoom to 14

#### Scenario: New section has no map position
- **WHEN** a new section is created and the map picker is opened
- **THEN** the map centers on the survey's default position and "Inherit position" is checked

#### Scenario: Set map position by search
- **WHEN** the user opens the map picker for a section with "Inherit position" checked, types "Tallinn" and chooses the result, then saves
- **THEN** the section's start_map_position is the result point, its zoom the result's zoom, and "Inherit position" is unchecked

#### Scenario: Click and save without using the place search
- **WHEN** the user opens the picker, unticks "Inherit position", clicks the map at a new point and clicks "Save Position" without touching the place search
- **THEN** the clicked coordinates are posted and persisted, and reopening the picker shows them rather than the inherited position

#### Scenario: Picker declares its own Mapbox credentials
- **WHEN** any editor template rendering a map picker is loaded
- **THEN** it reads the Mapbox token from the template context rather than from a variable declared by an enclosing template
