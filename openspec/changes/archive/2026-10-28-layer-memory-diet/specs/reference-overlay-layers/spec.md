# reference-overlay-layers — delta for layer-memory-diet

## MODIFIED Requirements

### Requirement: Creator uploads and configures a reference layer
An owner SHALL be able to upload a GeoJSON file (≤10 MB, WGS84, ≤5000 features,
≤10 layers per survey) that becomes a `SurveyMapLayer` with configurable name, color
(`#RRGGBB`), label field, key field, and info-popups flag. The stored GeoJSON SHALL be
derived from the layer's objects (never the raw upload bytes). The upload SHALL be parsed
into a feature tree exactly once, objects SHALL be written in batches, and the derived
GeoJSON SHALL be assembled one feature at a time rather than from a whole-collection tree.
The union of feature property names SHALL be stored on the layer when it is rebuilt and
returned by the upload so label/key fields are picked from a dropdown, not typed; no
editor surface SHALL parse the stored GeoJSON to list property names. Invalid files
SHALL be rejected with a human-readable reason.

#### Scenario: Successful upload
- **WHEN** the owner uploads a valid 148 KB FeatureCollection of 35 zone polygons
- **THEN** a layer is created, the response lists its property names, and the editor card shows name, feature count and size

#### Scenario: Property names come from the layer, not a parse
- **WHEN** the editor renders the settings card for a survey with a 10 MB layer
- **THEN** the card lists the layer's property names without selecting or parsing the stored GeoJSON

#### Scenario: Derived GeoJSON is unchanged by the streaming assembly
- **WHEN** a layer with categories, cover images and reserved properties is rebuilt
- **THEN** the stored FeatureCollection is byte-identical to the previous whole-tree serialisation

#### Scenario: Projected-CRS file rejected
- **WHEN** an uploaded file contains coordinates outside lng [-180,180] / lat [-90,90]
- **THEN** the upload is rejected with a message pointing at a non-WGS84 coordinate system

#### Scenario: Oversized file rejected
- **WHEN** the upload exceeds 10 MB
- **THEN** it is rejected before full processing with a size message

#### Scenario: Non-owner cannot manage layers
- **WHEN** a user without the owner role POSTs to any layer endpoint
- **THEN** the request is refused

### Requirement: Layer geometry is served by a gated cacheable endpoint
Layer GeoJSON SHALL be served at `GET /surveys/<uuid>/layers/<id>.geojson` under the
same access rules as the survey's section pages, with an `ETag` derived from the
layer's `updated_at` and private caching. The derived GeoJSON SHALL be stored
gzip-compressed and served as-is with `Content-Encoding: gzip`; the application SHALL
decompress it only on paths that read its content (export, tallies). Layer GeoJSON SHALL
NOT be inlined into the respondent HTML and SHALL NOT be exposed at a public storage URL.
Surfaces that read a layer's configuration SHALL NOT load its geometry column.

#### Scenario: Draft survey layer hidden from outsiders
- **WHEN** an anonymous request fetches a layer of an unpublished survey without a test link
- **THEN** the endpoint refuses as the survey page itself would

#### Scenario: Conditional revalidation
- **WHEN** a client re-requests with a matching `If-None-Match`
- **THEN** the endpoint returns 304 with no body

#### Scenario: Compressed delivery
- **WHEN** a client fetches a layer
- **THEN** the body is the stored gzip bytes with `Content-Encoding: gzip` and `Content-Type: application/geo+json`, and a browser `fetch()` receives the FeatureCollection unchanged
