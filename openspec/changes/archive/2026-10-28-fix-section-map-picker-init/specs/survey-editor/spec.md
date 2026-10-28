## MODIFIED Requirements

### Requirement: Section map position picker
The system SHALL provide a Leaflet map picker for setting a section's start_map_position and start_map_zoom. The picker SHALL open in a wide modal, display a map centered at the section's current position, and allow the user to click to set a new position and adjust zoom. The picker SHALL include the shared place search above the map; choosing a search result SHALL move the map to the place, set the picked position to the result point and the zoom to the result's zoom, uncheck "Inherit position" if it was checked, and update the coordinates label. On viewports of 1024px and wider the map SHALL be at least 480px tall; narrower viewports keep the previous height. The picker's click, zoom, "Inherit position" and Save handlers SHALL be bound before the place-search control is attached, and the picker SHALL pass the Mapbox token to that control as a template literal rather than reading a global declared by another partial, so that a failure to initialise the search control cannot disable the picker.

#### Scenario: Set map position by clicking
- **WHEN** the user opens the map picker for a section and clicks on the map at coordinates (30.5, 60.0) with zoom level 14
- **THEN** the section's start_map_postion is updated to POINT(30.5 60.0) and start_map_zoom is updated to 14

#### Scenario: Set map position by clicking without searching first
- **WHEN** the user opens the map picker for a section that inherits its position, unticks "Inherit position", clicks the map and presses "Save Position" without having used the place search
- **THEN** the click is registered, the coordinates label shows the clicked point, and the section's start_map_postion and start_map_zoom equal the clicked point and the current zoom

#### Scenario: Default position for new sections
- **WHEN** a new section is created and the map picker is opened
- **THEN** the map is centered at the default position POINT(30.317 59.945) with zoom 12

#### Scenario: Set map position by search
- **WHEN** the user opens the map picker for a section with "Inherit position" checked, types "Tallinn" and chooses the result, then saves
- **THEN** "Inherit position" is unchecked, the marker sits on the result point, and the section's start_map_postion and start_map_zoom equal the result's point and zoom

#### Scenario: Picker without a geocoder token
- **WHEN** `MAPBOX_ACCESS_TOKEN` is empty
- **THEN** the picker renders and works by click exactly as before, with no search box

#### Scenario: Picker survives a search control that fails to initialise
- **WHEN** attaching the place-search control throws during the picker's initialisation
- **THEN** clicking the map, toggling "Inherit position" and "Save Position" still work, because they were bound before the control was attached

#### Scenario: Picker declares what it uses
- **WHEN** the section map picker renders
- **THEN** the script passes the Mapbox token as a literal and contains no reference to a `mapboxAccessToken` global
