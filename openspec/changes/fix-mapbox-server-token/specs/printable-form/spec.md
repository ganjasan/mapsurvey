## MODIFIED Requirements

### Requirement: The map image degrades without a basemap
The basemap SHALL be requested with `MAPBOX_SERVER_TOKEN`, or with `MAPBOX_ACCESS_TOKEN` when
`MAPBOX_SERVER_TOKEN` is empty; the server token SHALL never be rendered into a page.
The frame SHALL print as an empty box with a 10 mm grid and the text "Map unavailable — attach a
printed map here" when both tokens are empty, the Static Images request fails or it
exceeds 5 seconds; the layers SHALL still be drawn when a position is known, the `PrintedForm`
layout entry SHALL record `basemap: null`, and the view SHALL still answer the PDF. Successful
images SHALL be cached for 24 hours by style, centre, zoom and size.

#### Scenario: No token
- **GIVEN** both Mapbox tokens empty
- **WHEN** a map section is printed
- **THEN** the PDF is returned, the frame text says the map is unavailable and the layout records a null basemap

#### Scenario: Server token wins
- **GIVEN** `MAPBOX_SERVER_TOKEN` and `MAPBOX_ACCESS_TOKEN` both set
- **WHEN** the basemap is fetched
- **THEN** the Static Images request carries the server token

#### Scenario: Public token as fallback
- **GIVEN** `MAPBOX_SERVER_TOKEN` empty and `MAPBOX_ACCESS_TOKEN` set
- **WHEN** the basemap is fetched
- **THEN** the Static Images request carries the public token

#### Scenario: Cached second print
- **WHEN** the same frame is printed twice within a day
- **THEN** the Static Images API is called once
