## ADDED Requirements

### Requirement: No tiles from volunteer-run servers
No Mapsurvey surface SHALL request map tiles from a volunteer-run tile server, including
`tile.openstreetmap.org` and `tile.opentopomap.org`. Tile providers SHALL be services the project
holds an account with (Mapbox, Esri).

#### Scenario: Respondent survey page
- **WHEN** a respondent loads a survey section page with any combination of basemaps enabled
- **THEN** the rendered HTML contains no `tile.openstreetmap.org` or `tile.opentopomap.org` URL

#### Scenario: Public results page
- **WHEN** anyone loads `/r/<slug>/` for a page containing a map block
- **THEN** the rendered HTML contains no `tile.openstreetmap.org` or `tile.opentopomap.org` URL

#### Scenario: Editor surfaces
- **WHEN** a creator loads the survey create wizard, the section map picker, or the analytics
  Response Map
- **THEN** the rendered HTML contains no `tile.openstreetmap.org` or `tile.opentopomap.org` URL

### Requirement: Topo basemap is served by Mapbox Outdoors
The `topo` basemap slug SHALL render Mapbox Outdoors tiles on every surface that offers it. The
tile URL SHALL come from the `MAPBOX_OUTDOORS_URL` setting rather than a template literal, and the
layer SHALL be attributed to Mapbox and OpenStreetMap.

#### Scenario: Topo enabled on a survey
- **WHEN** a survey has `topo` in `basemaps` and a respondent loads a section page
- **THEN** the page renders a tile layer built from `MAPBOX_OUTDOORS_URL` with the survey's Mapbox
  access token and an attribution naming both Mapbox and OpenStreetMap

#### Scenario: Style version is configurable
- **WHEN** `MAPBOX_OUTDOORS_URL` is set to a different Mapbox style URL in the environment
- **THEN** every surface offering `topo` renders that URL, with no template change

#### Scenario: Existing surveys need no migration
- **WHEN** a survey created before this change has `basemaps` containing `topo` or
  `default_basemap` set to `topo`
- **THEN** it keeps working unchanged and renders the Mapbox Outdoors layer under the same slug

### Requirement: One provider table for all surfaces
The basemap slugs `streets`, `satellite` and `topo` SHALL resolve to the same providers on every
surface. A template SHALL NOT define its own tile URLs for these slugs.

#### Scenario: Public results matches the respondent map
- **WHEN** a survey enables `streets` and `topo`, and the same survey has a public results page
- **THEN** both surfaces render the same tile URLs for those slugs, taken from settings

#### Scenario: Satellite is unaffected
- **WHEN** any surface renders the `satellite` basemap
- **THEN** it renders the Esri World Imagery tile URL, attributed to Esri, unchanged by this change
