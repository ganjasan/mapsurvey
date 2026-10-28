## MODIFIED Requirements

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

### Requirement: Layer geometry is served by a gated cacheable endpoint
Layer GeoJSON SHALL be served at `GET /surveys/<uuid>/layers/<id>.geojson` under the
same access rules as the survey's section pages, with an `ETag` derived from the layer's
`updated_at` and private caching. The served document SHALL be the GeoJSON derived from the
layer's objects, carrying the reserved `_key`, `_title`, `_category`, `_has_content` and
`_cover` properties. Layer GeoJSON SHALL NOT be inlined into the respondent HTML and SHALL
NOT be exposed at a public storage URL. Layers SHALL resolve to the canonical survey for
draft copies and archived versions.

#### Scenario: Draft survey layer hidden from outsiders
- **WHEN** an anonymous request fetches a layer of an unpublished survey without a test link
- **THEN** the endpoint refuses as the survey page itself would

#### Scenario: Conditional revalidation
- **WHEN** a client re-requests with a matching `If-None-Match`
- **THEN** the endpoint returns 304 with no body

#### Scenario: Version reads canonical layers
- **WHEN** a respondent loads an archived version's page (or a creator loads a draft copy's preview)
- **THEN** the layer list and geometry are the canonical survey's
