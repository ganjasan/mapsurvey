## MODIFIED Requirements

### Requirement: Section map position picker
The system SHALL provide a Leaflet map picker for setting a section's start_map_position and start_map_zoom. The picker SHALL open in a wide modal, display a map centered at the section's current position, and allow the user to click to set a new position and adjust zoom. The picker SHALL include the shared place search above the map; choosing a search result SHALL move the map to the place, set the picked position to the result point and the zoom to the result's zoom, uncheck "Inherit position" if it was checked, and update the coordinates label. On viewports of 1024px and wider the map SHALL be at least 480px tall; narrower viewports keep the previous height.

#### Scenario: Set map position by clicking
- **WHEN** the user opens the map picker for a section and clicks on the map at coordinates (30.5, 60.0) with zoom level 14
- **THEN** the section's start_map_postion is updated to POINT(30.5 60.0) and start_map_zoom is updated to 14

#### Scenario: Default position for new sections
- **WHEN** a new section is created and the map picker is opened
- **THEN** the map is centered at the default position POINT(30.317 59.945) with zoom 12

#### Scenario: Set map position by search
- **WHEN** the user opens the map picker for a section with "Inherit position" checked, types "Tallinn" and chooses the result, then saves
- **THEN** "Inherit position" is unchecked, the marker sits on the result point, and the section's start_map_postion and start_map_zoom equal the result's point and zoom

#### Scenario: Picker without a geocoder token
- **WHEN** `MAPBOX_ACCESS_TOKEN` is empty
- **THEN** the picker renders and works by click exactly as before, with no search box

## ADDED Requirements

### Requirement: Survey default map position picker
The survey settings page and the in-editor settings panel SHALL provide a Leaflet map picker for the survey's start_map_position, start_map_zoom and use_geolocation, with the shared place search above the map. Choosing a search result SHALL move the map, set the picked position to the result point and the zoom to the result's zoom, and update the coordinates label; a subsequent click SHALL still refine the position. On viewports of 1024px and wider the settings-page map SHALL be at least 460px tall and its section SHALL be allowed to exceed the 800px settings column; the in-editor panel map SHALL be at least 380px tall. Narrower viewports keep the previous heights.

#### Scenario: Move a survey to another city by search
- **WHEN** a creator opens survey settings for a survey positioned in Berlin, searches "Ülemiste, Tallinn", chooses the result and clicks "Save Map Position"
- **THEN** the survey's start_map_postion is the result point, start_map_zoom is the result's zoom, and the coordinates label showed the new values before saving

#### Scenario: Search box present on both settings surfaces
- **WHEN** the standalone settings page and the in-editor settings panel render with a Mapbox token configured
- **THEN** each contains one place-search input directly above its map picker

#### Scenario: Desktop map is not cramped
- **WHEN** the standalone settings page renders at 1280px width
- **THEN** the map picker is at least 460px tall and wider than the 800px settings column
