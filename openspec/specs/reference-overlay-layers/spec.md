# reference-overlay-layers Specification

## Purpose

Creator-uploaded GeoJSON layers rendered read-only beneath the respondent map —
counting zones, boundaries, routes, a plan under discussion — covering the layer
lifecycle, respondent rendering rules, per-section visibility and the gated
delivery endpoint.
## Requirements
### Requirement: Creator uploads and configures a reference layer
An owner SHALL be able to create a reference layer (≤10 layers per survey) with a
configurable name, color (`#RRGGBB`), label field, key field and info-popups flag, and
SHALL populate it with objects through the object editor — by drawing, by importing a
GeoJSON file (≤10 MB, WGS84, ≤5000 features) or by importing a CSV. Imported GeoJSON SHALL be
parsed feature-by-feature into objects; the raw upload bytes SHALL never be stored. Import
SHALL return the union of feature property names so title/category/description/link/key
mappings are picked from a dropdown, not typed. Invalid files SHALL be rejected with a
human-readable reason. `label_field` and `key_field` SHALL act as default mappings for
subsequent imports.

#### Scenario: Successful import
- **WHEN** the owner imports a valid 148 KB FeatureCollection of 35 zone polygons into a layer
- **THEN** 35 objects are created, the response lists the property names, and the layer card shows name, object count and size

#### Scenario: Projected-CRS file rejected
- **WHEN** an imported file contains coordinates outside lng [-180,180] / lat [-90,90]
- **THEN** the import is rejected with a message pointing at a non-WGS84 coordinate system

#### Scenario: Oversized file rejected
- **WHEN** the import exceeds 10 MB
- **THEN** it is rejected before full processing with a size message

#### Scenario: Non-owner cannot manage layers
- **WHEN** a user without the owner role POSTs to any layer or object endpoint
- **THEN** the request is refused

### Requirement: Respondent map renders reference layers beneath answers
On map-layout sections, the respondent map SHALL render the survey's reference layers
in a dedicated pane below answer geometry. Feature styling SHALL follow the layer's
`style`: a rule class by attribute when the layer has a rule, else simplestyle
properties in the feature (`stroke`, `fill`, `stroke-width`, `marker-color`,
`stroke-opacity`, `fill-opacity`), else the base style with the layer colour; point
features SHALL render as circle markers, or as glyph markers when an icon is set, never
default markers. When a label field is set, features SHALL show a permanent centered label
with the property value HTML-escaped. Layers with a rule and the legend flag SHALL show a
legend under their name in the layers control. Layers SHALL persist across HTMX section
navigation without refetching.

#### Scenario: Zones visible under observation markers
- **WHEN** a volunteer places observation points on a section whose survey has a zones layer
- **THEN** the zone polygons render beneath the markers, styled with the layer color and labeled from the label field

#### Scenario: Self-styled plan wins over layer color
- **WHEN** a layer's features carry simplestyle properties (e.g. green lawn, orange playground) and the layer has no rule
- **THEN** each feature renders in its own colors and the layer color is unused

#### Scenario: Rule wins over file colours
- **WHEN** the same layer gets a categories rule on `use`
- **THEN** each feature renders in its class colour and the file's simplestyle is unused

#### Scenario: Label values are escaped
- **WHEN** a feature's label property contains `<img onerror=...>`
- **THEN** the label displays the literal text and no HTML executes

#### Scenario: Layers survive section navigation
- **WHEN** the respondent moves to the next section via HTMX
- **THEN** visible layers remain on the map without a new fetch of layer geometry

#### Scenario: Legend in the layers control
- **WHEN** a layer with a four-class rule is visible on the section
- **THEN** the layers control shows its name and four legend rows

### Requirement: Reference layers never intercept answering
Reference-layer features SHALL NOT be selectable, editable, or draggable by respondents.
With info popups disabled and the layer not bound to a `layer_objects` question, the layer
SHALL be fully non-interactive. With info popups enabled on an unbound layer, clicking a
feature SHALL show an escaped read-only popup of its title and description properties. On a
layer bound to a `layer_objects` question, clicking a feature SHALL open the object popup
defined by `layer-objects-question`. In every case, placing answer geometry by tapping the
map SHALL continue to work over layer features while a draw mode is active.

#### Scenario: Tap over a zone places the answer
- **WHEN** a respondent in point-placement mode taps inside a zone polygon (popups disabled)
- **THEN** an answer point is placed exactly as on bare map

#### Scenario: Popup shows plan details
- **WHEN** popups are enabled on an unbound layer and a respondent clicks the "playground" polygon outside placement mode
- **THEN** a popup shows the object's escaped title and description and the geometry cannot be modified

#### Scenario: Bound layer opens the object popup
- **WHEN** a layer is bound to a `layer_objects` question and a respondent clicks one of its features outside placement mode
- **THEN** the object popup with the card and sub-questions opens

### Requirement: Layer visibility is controllable per section and by the respondent
Each section SHALL be able to hide any subset of the survey's layers
(`hidden_layers`; default — all visible; unknown IDs ignored). The respondent SHALL be
able to toggle each visible layer via the Leaflet layers control, which SHALL appear
whenever at least one reference layer is visible. Form-layout sections render no map
and therefore no layers.

#### Scenario: Section hides a layer
- **WHEN** a section lists a layer in `hidden_layers` and the respondent navigates to it
- **THEN** that layer is removed from the map and re-added on a section where it is not hidden

#### Scenario: Respondent toggles a layer off
- **WHEN** the respondent unchecks the layer in the layers control
- **THEN** the overlay disappears; answer geometry is unaffected

### Requirement: Layer geometry is served by a gated cacheable endpoint
Layer GeoJSON SHALL be served at `GET /surveys/<uuid>/layers/<id>.geojson` under the
same access rules as the survey's section pages. For `upload` layers the response SHALL
carry an `ETag` derived from the layer's `updated_at` and private caching. For `question`
layers the response SHALL be computed per request — only `visible` objects from clean
sessions other than the requesting session — with an `ETag` that also includes the
requesting session id and `Cache-Control: private, no-store`. The served document SHALL be
the GeoJSON derived from the layer's objects, carrying the reserved `_key`, `_title`,
`_category`, `_has_content` and `_cover` properties, plus `tally_up`, `tally_down` and
`comment_count` on `question` layers with `show_tallies`. Layer GeoJSON SHALL NOT be
inlined into the respondent HTML and SHALL NOT be exposed at a public storage URL. Layers
SHALL resolve to the canonical survey for draft copies and archived versions.

#### Scenario: Draft survey layer hidden from outsiders
- **WHEN** an anonymous request fetches a layer of an unpublished survey without a test link
- **THEN** the endpoint refuses as the survey page itself would

#### Scenario: Conditional revalidation
- **WHEN** a client re-requests an `upload` layer with a matching `If-None-Match`
- **THEN** the endpoint returns 304 with no body

#### Scenario: Version reads canonical layers
- **WHEN** a respondent loads an archived version's page (or a creator loads a draft copy's preview)
- **THEN** the layer list and geometry are the canonical survey's

#### Scenario: Question layer is per session
- **WHEN** two respondents fetch the same `question` layer
- **THEN** each receives a collection without their own marks, the ETags differ, and neither response is stored by a shared cache

### Requirement: Feature kill switch
With `MAP_REFERENCE_LAYERS` off, the editor SHALL NOT render layer management UI, the
respondent page SHALL receive no layer metadata, and layer endpoints SHALL return 404.
Stored layers SHALL be preserved.

#### Scenario: Flag off hides everything, loses nothing
- **WHEN** the flag is turned off and later on again
- **THEN** no layer surface renders while off, and all layers reappear unchanged after

### Requirement: The editor preview renders reference layers
The editor's section preview SHALL render the survey's reference layers on its map with
the same styling, labels and per-section visibility as the respondent page, so a creator
verifying an upload sees what respondents will see.

#### Scenario: Uploaded layer appears in the preview
- **WHEN** a creator uploads a layer and opens a map section in the editor
- **THEN** the preview iframe carries that layer's config and its geometry URL

#### Scenario: Preview honours per-section visibility
- **WHEN** the previewed section hides a layer
- **THEN** the preview marks that layer hidden, exactly as the respondent page does

#### Scenario: Kill switch applies to the preview too
- **WHEN** `MAP_REFERENCE_LAYERS` is off
- **THEN** the preview carries no layer config

