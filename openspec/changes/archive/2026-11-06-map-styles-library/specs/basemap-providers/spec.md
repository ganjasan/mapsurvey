## MODIFIED Requirements

### Requirement: Topo basemap is served by Mapbox Outdoors
The `topo` basemap key SHALL render Mapbox Outdoors tiles on every surface that offers it. The style id SHALL come from the `topo` preset row of the map style library (`mapbox/outdoors-v12`), the tile URL from `MAPBOX_TILES_URL` with that id, and the layer SHALL be attributed to Mapbox and OpenStreetMap.

#### Scenario: Topo enabled on a survey
- **WHEN** a survey has `topo` in `basemaps` and a respondent loads a section page
- **THEN** the page renders a tile layer built from `MAPBOX_TILES_URL` with `mapbox/outdoors-v12` and the survey's Mapbox access token, and an attribution naming both Mapbox and OpenStreetMap

#### Scenario: Tile template is configurable
- **WHEN** `MAPBOX_TILES_URL` is set to a different template in the environment
- **THEN** every surface offering a Mapbox preset renders that template, with no template change

#### Scenario: Existing surveys need no migration
- **WHEN** a survey created before this change has `basemaps` containing `topo` or `default_basemap` set to `topo`
- **THEN** it keeps working unchanged and renders the Mapbox Outdoors layer under the same key

### Requirement: One provider table for all surfaces
Every basemap key SHALL resolve to the same provider on every surface through `survey/basemaps.py`, and every Mapbox layer SHALL be requested as 512-px tiles with `tileSize: 512` and `zoomOffset: -1`. A template SHALL NOT define its own tile URLs or Leaflet tile options for any key.

#### Scenario: Public results matches the respondent map
- **WHEN** a survey enables `streets` and `topo`, and the same survey has a public results page
- **THEN** both surfaces render the same tile URLs and tile options for those keys, taken from the resolver

#### Scenario: Satellite is unaffected
- **WHEN** any surface renders the `satellite` basemap
- **THEN** it renders the Esri World Imagery tile URL from the `satellite` preset row, attributed to Esri, as 256-px tiles

#### Scenario: Streets-only surfaces use the same entry
- **WHEN** the settings map picker, the reference-layer style preview, the Responses overview thumbnail or the Responses map modal renders its map
- **THEN** its tile layer is built from the resolver's `streets` entry (URL and options), not from a literal in the template
