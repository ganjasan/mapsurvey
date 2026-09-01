## ADDED Requirements

### Requirement: The Responses Map pane renders reference layers
The Responses tab's Map pane SHALL render every reference layer of the survey beneath answer
geometry, each in its own pane, with the same styling, simplestyle handling, circle-marker
points and escaped permanent labels as the respondent map. All layers SHALL be shown
regardless of any section's `hidden_layers`. Each layer SHALL appear as a row in a titled
"Reference layers" group of the Map pane's Layers panel, visually separate from and beneath
the answer layers — checkbox, colour swatch, name, zoom-to — ordered by survey position on
first load (position 0 at the bottom); the creator SHALL be able to switch a layer off, drag
rows within the group to change the stacking order (the top row draws on top; reference
layers never rise above an answer layer), and set the layer's opacity from 0 to 100 %.
Visibility, order and opacity SHALL be remembered per survey in the creator's browser and
SHALL NOT affect the respondent map, the editor preview or other users. Layer features SHALL
be non-interactive on this map irrespective of the layer's info-popups setting. When the
survey has at least one reference layer, the Map pane SHALL render its map even if no geo
answer exists yet, fitted to the union of the layers. Layer geometry SHALL be fetched from the
gated layer endpoint, once per dashboard page load, and SHALL NOT be inlined into the
dashboard HTML.

#### Scenario: Zones under the collected points
- **WHEN** a creator opens the Responses Map pane of a survey with a zones layer and 40 point answers
- **THEN** the zone polygons render beneath the points, styled with the layer color and labeled from the label field, and the Layers panel lists "Zones" checked beneath the answer layers

#### Scenario: Section-hidden layer still shows on Responses
- **WHEN** a layer is listed in one section's `hidden_layers`
- **THEN** the Responses Map pane still renders that layer

#### Scenario: Stacking follows the panel, not the network
- **WHEN** a survey has a large boundary layer at position 0 and a small zones layer at position 1, and the zones file arrives first
- **THEN** the boundary still draws beneath the zones, and dragging the boundary row above the zones row puts it on top

#### Scenario: Reference group is distinct from answers
- **WHEN** the Layers panel renders a survey with one geo question and three reference layers
- **THEN** the question is listed first, a "Reference layers" title separates the group, the three layers follow it, and a reference row cannot be dropped among the answer rows

#### Scenario: Opacity and order survive a reload
- **WHEN** the creator sets a layer to 30 % opacity, drags it to the top and reloads the page
- **THEN** the layer renders at 30 % on top, while a respondent opening the survey sees it at full opacity in its stored position

#### Scenario: Selecting a point over a zone
- **WHEN** the creator clicks an answer point that lies inside a zone polygon whose layer has info popups enabled
- **THEN** the answer's popup/selection behaviour fires and no reference-layer popup opens

#### Scenario: Map appears before the first answer
- **WHEN** the survey has a reference layer and zero geo answers
- **THEN** the Map pane renders the map with the layer and a "(0 features)" heading instead of an empty pane

#### Scenario: Zero answers, two distant layers
- **WHEN** the survey has no geo answers and two layers in different parts of the city
- **THEN** the map fits both layers, not just the one that loaded first

#### Scenario: Geometry is not in the page
- **WHEN** the dashboard HTML is rendered for a survey with a 2 MB layer
- **THEN** the HTML carries only the layer metadata (id, name, color, label field, URL) and the geometry is fetched from the layer endpoint

### Requirement: The response map modal and the Overview thumbnail render reference layers
The response map modal and the Overview thumbnail SHALL render the survey's reference layers
beneath the answer geometry with the same styling, visibility, order and opacity as the Map
pane's Layers panel, reusing geometry already fetched on the page rather than requesting it
again.
The Overview thumbnail SHALL reflect changes made in the Layers panel when the creator returns
to Overview. The session mini-map thumbnail in the response drawer SHALL NOT render reference
layers.

#### Scenario: One response against the plan
- **WHEN** the creator opens the full-size map of a response on a survey with a plan layer
- **THEN** the plan renders beneath the response's geometry and no additional layer request is issued

#### Scenario: Overview thumbnail shows the layers
- **WHEN** the creator opens the Responses tab of a survey with reference layers and stays on Overview
- **THEN** the Response Map thumbnail draws the layers beneath the answers as they arrive, without a request beyond the ones the Map pane makes

#### Scenario: Overview follows the panel
- **WHEN** the creator hides one layer and dims another on the Map pane, then returns to Overview
- **THEN** the thumbnail omits the hidden layer and draws the dimmed one at the chosen opacity

#### Scenario: Drawer thumbnail stays bare
- **WHEN** the session detail drawer renders its mini-map
- **THEN** no reference layer is drawn on the thumbnail

## MODIFIED Requirements

### Requirement: Creator uploads and configures a reference layer
An owner SHALL be able to upload a GeoJSON file (≤10 MB, WGS84, ≤5000 features,
≤10 layers per survey) that becomes a `SurveyMapLayer` with configurable name, color
(`#RRGGBB`), label field, key field, and info-popups flag. The stored GeoJSON SHALL be
the re-serialized parse of the upload, never the raw bytes. Upload SHALL return the
union of feature property names so label/key fields are picked from a dropdown, not
typed. Invalid files SHALL be rejected with a human-readable reason.

#### Scenario: Successful upload
- **WHEN** the owner uploads a valid 148 KB FeatureCollection of 35 zone polygons
- **THEN** a layer is created, the response lists its property names, and the editor card shows name, feature count and size

#### Scenario: Projected-CRS file rejected
- **WHEN** an uploaded file contains coordinates outside lng [-180,180] / lat [-90,90]
- **THEN** the upload is rejected with a message pointing at a non-WGS84 coordinate system

#### Scenario: Oversized file rejected
- **WHEN** the upload exceeds 10 MB
- **THEN** it is rejected before full processing with a size message

#### Scenario: Non-owner cannot manage layers
- **WHEN** a user without the owner role POSTs to any layer endpoint
- **THEN** the request is refused

#### Scenario: Eleventh layer refused
- **WHEN** a survey already holds 10 reference layers and the owner uploads another
- **THEN** the upload is refused with a message naming the 10-layer limit and no layer is created


### Requirement: Layer geometry is served by a gated cacheable endpoint
Layer GeoJSON SHALL be served at `GET /surveys/<uuid>/layers/<id>.geojson` under the
same access rules as the survey's section pages, with an `ETag` derived from the
layer's `updated_at` and private caching. An authenticated user whose effective role on the
survey is `viewer` or higher SHALL be served the layer in every survey status (draft, testing,
published, closed, archived); this bypass SHALL apply to the layer endpoint only and SHALL NOT
change access to the survey's section pages. Layer GeoJSON SHALL NOT be inlined into the
respondent HTML and SHALL NOT be exposed at a public storage URL.

#### Scenario: Draft survey layer hidden from outsiders
- **WHEN** an anonymous request fetches a layer of an unpublished survey without a test link
- **THEN** the endpoint refuses as the survey page itself would

#### Scenario: Conditional revalidation
- **WHEN** a client re-requests with a matching `If-None-Match`
- **THEN** the endpoint returns 304 with no body

#### Scenario: Viewer fetches a draft survey's layer
- **WHEN** a user holding the `viewer` role on a draft survey fetches its layer
- **THEN** the GeoJSON is returned with private caching

#### Scenario: Owner fetches a closed survey's layer
- **WHEN** the owner fetches a layer of a closed survey
- **THEN** the GeoJSON is returned

#### Scenario: Outsider still refused on a closed survey
- **WHEN** an anonymous request, or an authenticated user with no role on the survey, fetches a layer of a closed survey
- **THEN** the endpoint returns 404

### Requirement: Feature kill switch
With `MAP_REFERENCE_LAYERS` off, the editor SHALL NOT render layer management UI, the
respondent page SHALL receive no layer metadata, the Responses tab SHALL receive no layer
metadata and SHALL render no layer loader, and layer endpoints SHALL return 404.
Stored layers SHALL be preserved.

#### Scenario: Flag off hides everything, loses nothing
- **WHEN** the flag is turned off and later on again
- **THEN** no layer surface renders while off, and all layers reappear unchanged after

#### Scenario: Flag off on the Responses tab
- **WHEN** the flag is off and a creator opens the Responses tab of a survey that has layers
- **THEN** the dashboard HTML contains no layer metadata and no layer URL
