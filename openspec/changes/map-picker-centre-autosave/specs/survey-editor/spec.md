## MODIFIED Requirements

### Requirement: Section map position picker
The system SHALL provide a Leaflet map picker for setting a section's start_map_position and start_map_zoom. The picker SHALL open in a wide modal and display the map centred on the section's own position, or on the survey's default position when the section has none. The position SHALL be the centre of the map and the zoom its zoom level: a fixed pin SHALL mark the centre, and dragging, zooming, choosing a place-search result and "My location" SHALL each move the map and thereby set the position. The picker SHALL NOT take a position from a click. Every settled move SHALL be saved automatically (debounced) through the section map-position endpoint, and a status indicator SHALL show saving, saved, or a failure with a retry; the modal SHALL have no Save button. The picker SHALL include the shared place search above the map. On viewports of 1024px and wider the map SHALL be at least 480px tall; narrower viewports keep the previous height.

An "Inherit position" checkbox SHALL be ticked when the section has no position of its own. Ticking it SHALL fly the map to the survey's default position, dim the pin, show that the section inherits, and save the cleared position at once. While it is ticked, movement of the map SHALL NOT be saved. Any creator gesture on the map — drag, scroll-wheel or pinch zoom, the zoom control, a place-search result, "My location" — SHALL untick it, after which the resulting centre is saved; programmatic moves SHALL NOT untick it. The section's geolocation flag and basemap override SHALL save on change through the same call.

#### Scenario: Set map position by dragging
- **WHEN** the user opens the picker for a section, unticks "Inherit position", drags the map so its centre is (60.0, 30.5) at zoom 14 and stops
- **THEN** the label shows those coordinates, the indicator shows "Saved", and the section's start_map_postion is POINT(30.5 60.0) with start_map_zoom 14 — without any click on the map or on a button

#### Scenario: Reopening shows the saved position
- **WHEN** the user closes the picker after the previous scenario and opens it again
- **THEN** the map opens centred on (60.0, 30.5) at zoom 14 with the pin on the centre and "Inherit position" unticked

#### Scenario: Dragging while inherit is ticked sets an own position
- **WHEN** the user opens the picker for a section with no position ("Inherit position" ticked) and drags the map
- **THEN** "Inherit position" is unticked by the drag, and the centre where the drag settles is saved as the section's own position

#### Scenario: Ticking inherit flies to the default and clears
- **WHEN** the user ticks "Inherit position" on a section that has its own position
- **THEN** the map flies to the survey's default position and zoom, the pin is dimmed, the label says the section inherits, the section's start_map_postion and start_map_zoom are cleared, and the fly itself saves nothing else

#### Scenario: Default position for new sections
- **WHEN** a new section is created and the map picker is opened
- **THEN** the map is centred on the survey's default position with "Inherit position" ticked

#### Scenario: Set map position by search
- **WHEN** the user opens the map picker for a section with "Inherit position" ticked, types "Tallinn" and chooses the result
- **THEN** "Inherit position" is unticked, the map centres on the result at the result's zoom, and the section's start_map_postion and start_map_zoom equal that centre and zoom

#### Scenario: Save fails
- **WHEN** a save request fails (network error, or the survey became read-only)
- **THEN** the indicator shows a failure and a tap on it retries; nothing is silently dropped

#### Scenario: Picker without a geocoder token
- **WHEN** `MAPBOX_ACCESS_TOKEN` is empty
- **THEN** the picker renders and saves by dragging exactly as above, with no search box

### Requirement: Survey default map position picker
The survey settings page and the in-editor settings panel SHALL provide a Leaflet map picker for the survey's start_map_position, start_map_zoom and use_geolocation, with the shared place search above the map. The position SHALL be the centre of the map and the zoom its zoom level: a fixed pin SHALL mark the centre, and dragging, zooming, choosing a search result and "My location" SHALL each move the map and thereby set the position; the picker SHALL NOT take a position from a click. Every settled move SHALL be saved automatically (debounced) through the survey map-position endpoint, the geolocation flag SHALL save on change, and a status indicator SHALL show saving, saved, or a failure with a retry; there SHALL be no Save button. On viewports of 1024px and wider the settings-page map SHALL be at least 460px tall and its section SHALL be allowed to exceed the 800px settings column; the in-editor panel map SHALL be at least 380px tall. Narrower viewports keep the previous heights.

#### Scenario: Move a survey to another city by search
- **WHEN** a creator opens survey settings for a survey positioned in Berlin, searches "Ülemiste, Tallinn" and chooses the result
- **THEN** the map centres on the result, the label shows the new coordinates, the indicator shows "Saved", and the survey's start_map_postion and start_map_zoom are the result's centre and zoom

#### Scenario: Move a survey by dragging
- **WHEN** a creator drags the settings-panel map so its centre is (59.437, 24.7536) at zoom 12 and stops
- **THEN** the survey's start_map_postion is POINT(24.7536 59.437) and start_map_zoom 12, with no button pressed

#### Scenario: Search box present on both settings surfaces
- **WHEN** the standalone settings page and the in-editor settings panel render with a Mapbox token configured
- **THEN** each contains one place-search input directly above its map picker

#### Scenario: Desktop map is not cramped
- **WHEN** the standalone settings page renders at 1280px width
- **THEN** the map picker is at least 460px tall and wider than the 800px settings column
