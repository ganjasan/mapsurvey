## ADDED Requirements

### Requirement: Minimal survey creation
The Create New Survey page SHALL ask only for the survey name, the available
languages, and the map respondents will see — framed as "the map people will
see", not "your survey area".

The map block SHALL be WYSIWYG: the picker shows exactly the view respondents
open on, the map CENTRE is the survey's start position, and a fixed centre pin
marks it. The start position and zoom SHALL be kept in sync with the map centre
live (so a point is always set — the creator never has to click to drop a
marker), and framing the map via drag, place search, "My location", or creator
auto-geolocation SHALL update it. The base map SHALL be chosen through an on-map
dropdown control (a compact toggle, top-right, that opens a click-to-select menu
with icons — not a permanently-expanded radio list) that both switches the
preview and sets the survey's default base map; all base maps remain available
to respondents.

All other survey configuration (redirect URL, visibility, thanks page, cover
image, which base maps are enabled, and the respondent auto-center behavior)
SHALL NOT appear on the creation form; a newly created survey SHALL receive the
model defaults for those fields, and the page SHALL point the creator to the
Survey settings panel for them.

#### Scenario: Create with name only
- **WHEN** a creator submits the form with just a name (languages and map
  untouched)
- **THEN** the survey is created with default settings (private visibility,
  `#` redirect, all basemaps enabled, empty thanks/languages, auto-center off)
  and the creator lands in the Build space

#### Scenario: Create with languages chosen
- **WHEN** a creator picks one or more languages before submitting
- **THEN** the created survey stores exactly those `available_languages`

#### Scenario: The framed map centre becomes the start position
- **WHEN** a creator frames the map (drag / search / My location) so a place
  sits under the centre pin, then submits
- **THEN** the created survey stores the map centre and zoom as its start
  position — i.e. exactly the view respondents will open on

#### Scenario: Pick the base map from the on-map dropdown
- **WHEN** a creator opens the layers control on the map and selects Satellite
  (or Topo)
- **THEN** the picker preview switches to that provider and the created survey
  stores it as `default_basemap`, with all base maps still enabled; an unknown
  value is ignored

#### Scenario: Search the map for a place
- **WHEN** a creator types a place name into the map search and presses Enter
- **THEN** the map recentres on that place and the start position is set to it
  (no API key required — OpenStreetMap Nominatim)

#### Scenario: Jump to my location
- **WHEN** a creator clicks the "My location" button and grants geolocation
- **THEN** the map recentres on the creator's current position and the start
  position is set to it; if permission is denied the coords line explains how
  to set the area another way

#### Scenario: Full settings remain editable after creation
- **WHEN** the creator opens the Survey settings panel of the new survey
- **THEN** all the fields absent from the creation form (including the
  auto-center-on-respondent toggle) are present and editable there
