## ADDED Requirements

### Requirement: Ordered chain for a new survey's map start
The system SHALL provide one function, `survey.map_start.suggest_start_position`, that
returns a latitude, longitude, zoom and `source` for a new survey's map, trying in
order: `browser` (coordinates the request carries, present only when the creator's
browser supplied them), `org_survey` (the start position of the newest canonical,
non-deleted survey in the active organization that has one, with its zoom or 12),
`country` (the `CF-IPCountry` header when `CLOUDFLARE_TRUSTED` is on, otherwise the
region subtag of the first `Accept-Language` entry — except `en-US`, the stock-browser
default that says nothing about where the creator is — resolved through a country-centroid
table, zoom 5) and `world` (20, 0, zoom 2). The function SHALL never raise, SHALL make
no network request, and SHALL run at most one database query. Every survey creation
path — the blank endpoint, the create page's manual action and the AI draft — SHALL
open its map on this chain's result unless a stronger input (a creator-framed map or a
geocoded brief location) replaces it.

#### Scenario: Browser first
- **WHEN** the request carries browser coordinates and the organization has surveys with a start position
- **THEN** the browser coordinates are returned with `source='browser'`

#### Scenario: Organization's newest survey
- **WHEN** no browser coordinates are present and the organization has two surveys with start positions
- **THEN** the newer survey's position and zoom are returned with `source='org_survey'`

#### Scenario: Country from the edge
- **WHEN** no browser coordinates and no positioned survey exist, `CLOUDFLARE_TRUSTED` is on and `CF-IPCountry` is `KG`
- **THEN** the centroid of Kyrgyzstan at zoom 5 is returned with `source='country'`

#### Scenario: Edge header ignored when untrusted
- **WHEN** `CLOUDFLARE_TRUSTED` is off and `CF-IPCountry` is `KG` but `Accept-Language` is `de-AT,de;q=0.9`
- **THEN** the centroid of Austria is returned with `source='country'`

#### Scenario: Stock browser locale is not a location
- **WHEN** no trusted edge header exists and `Accept-Language` is `en-US,en;q=0.9`
- **THEN** the world view comes back, not the United States

#### Scenario: Unknown country falls through
- **WHEN** the resolved country code is not in the centroid table and nothing stronger exists
- **THEN** (20, 0) at zoom 2 is returned with `source='world'`

#### Scenario: Create page starts on the suggestion
- **WHEN** a creator whose organization surveys Bishkek opens `/editor/surveys/new/`
- **THEN** the map picker's initial view is the Bishkek survey's position, not Berlin

### Requirement: Browser position only with consent tied to an action
The system SHALL NOT request geolocation permission on page load. On the create page the
browser position SHALL be read silently only when the Permissions API reports
`granted`; when the server source is `country` or `world`, a one-line hint with a "Use my
location" link SHALL be shown above the map, and that link (and the on-map "My
location" button) is where permission is requested. On the start page, submitting
*Start from scratch* SHALL request permission when the state is `prompt`, wait at most
three seconds, and submit with the coordinates if given and without them otherwise.
Browsers without the Permissions API SHALL be treated as `prompt` on the start page and
as `denied` on the create page.

#### Scenario: Already granted
- **WHEN** a creator whose browser has granted geolocation opens the create page
- **THEN** no permission dialog appears and the map moves to the browser position

#### Scenario: Not yet asked, create page
- **WHEN** a creator whose browser state is `prompt` opens the create page and the server source is `world`
- **THEN** no dialog appears on load, the hint "Use my location" is shown, and clicking it triggers the permission request

#### Scenario: Asked on the blank click
- **WHEN** a creator whose browser state is `prompt` submits *Start from scratch*
- **THEN** the permission dialog appears, and the survey is created with the position when granted and without it when refused or after three seconds

#### Scenario: Refused is remembered by the browser
- **WHEN** a creator who refused earlier submits *Start from scratch*
- **THEN** no dialog appears and the survey is created from the server chain

### Requirement: Map source is measured
The `survey_created` event SHALL carry `map_source` with the chain's `source`, or `brief`
when the AI task replaced the position with a geocoded brief location, or `creator` when
the creator framed the create page's map (`map_touched=1`). The create page SHALL post the
initial source in a hidden `map_source` field.

#### Scenario: Blank from the world rung
- **WHEN** a blank survey is created with nothing but the world fallback
- **THEN** `survey_created` has `map_source='world'`

#### Scenario: Creator framed the map
- **WHEN** a creator drags the create page's map and submits the manual action
- **THEN** `survey_created` has `map_source='creator'`

#### Scenario: Geocoded brief
- **WHEN** an AI draft's brief names a place and the creator did not frame the map
- **THEN** `survey_created` has `map_source='brief'`
