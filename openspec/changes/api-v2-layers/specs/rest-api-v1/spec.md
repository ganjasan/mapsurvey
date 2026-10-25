## RENAMED Requirements

- FROM: `### Requirement: Layers are read-only and memory-safe`
- TO: `### Requirement: Layers are memory-safe`

## MODIFIED Requirements

### Requirement: Layers are memory-safe
`GET /surveys/{uuid}/layers` SHALL return layer metadata without selecting `geojson_gz`.
`GET /surveys/{uuid}/layers/{id}/geojson` SHALL serve the cached collection, passing the stored
gzip bytes through with `Content-Encoding: gzip` when the client accepts gzip. Layer and object
writes SHALL defer the geometry text the same way and SHALL never load a layer's `geojson` to change
its metadata.

#### Scenario: List path never loads geometry
- **WHEN** the layers list is requested under `LayerMemoryDietTest`'s query capture
- **THEN** no captured query selects `geojson_gz`

#### Scenario: Renaming a layer does not load its geometry
- **WHEN** a layer is renamed through the API under query capture
- **THEN** no captured query selects `geojson_gz`

## ADDED Requirements

### Requirement: Creating layers over the API
The API SHALL offer `POST /surveys/{uuid}/layers` (scope `surveys:write`, survey role `owner`)
taking a JSON body `{"name", "geojson"}`, and `POST /surveys/{uuid}/layers/upload` taking a multipart
`file` and `name`, validating either with
the editor's upload rules (at most 10 MB and 5 000 features, WGS84 coordinates only, Z dropped,
multi-part geometries split into one object per part) and creating the layer and its objects on the
canonical survey; without `geojson` or `file` it SHALL create an empty layer. A survey SHALL hold at
most 10 layers (`409 limit_reached`). The response SHALL be the layer with `live` saying whether
respondents see it now. The write SHALL be audited.

#### Scenario: Layer from inline GeoJSON
- **WHEN** an owner posts `{"name": "Benches", "geojson": <FeatureCollection of 3 points with a "name" property>}`
- **THEN** the response is 201 with `feature_count: 3` and the layer's objects are titled from `name`

#### Scenario: Projected coordinates
- **WHEN** the GeoJSON has coordinates in metres (e.g. `[392000, 5820000]`)
- **THEN** the response is `422 validation` saying to re-export as WGS84 and no layer exists

#### Scenario: Editor role is not enough
- **WHEN** a survey editor (not owner) posts a layer
- **THEN** the response is `403 forbidden_role`

### Requirement: Editing, ordering and deleting layers
`PATCH /surveys/{uuid}/layers/{id}` (owner) SHALL accept `name`, `color` (`#rrggbb`), `label_field`
and `key_field` (each a property of the layer or empty), `show_popups` and `style`, the style passing
`normalize_style`; a shared-map layer SHALL accept only name, color and style without a rule.
`PUT /surveys/{uuid}/layers/order` SHALL set the layers' order from a complete list of their ids.
`DELETE /surveys/{uuid}/layers/{id}` SHALL refuse a layer a question uses with `409 conflict` naming
the questions. Each write SHALL be audited.

#### Scenario: Style by category
- **WHEN** an owner patches `style.by = {"field": "kind", "mode": "categories", "classes": [...]}`
- **THEN** the stored style is the normalised one and the layer's `legend` lists the classes

#### Scenario: Layer in use
- **WHEN** an owner deletes a layer bound to the question "Rate these benches"
- **THEN** the response is 409 naming "Rate these benches" and the layer still exists

### Requirement: Layer objects over the API
The API SHALL list a layer's objects (`surveys:read`, cursor-paginated) and create, update and delete
them (`surveys:write`, owner) with `key` (unique in the layer, immutable after create), `title`,
`category`, `description` (through `coerce_creator_html`), `link` (http/https only), one-part
`geometry` and `properties`, within the layer's caps, rebuilding the layer after each write. Objects
of a shared-map layer SHALL be read-only (`409 conflict`). Each write SHALL be audited.

#### Scenario: Object with a script link
- **WHEN** an owner creates an object with `link: "javascript:alert(1)"`
- **THEN** the response is `422 validation` naming `link` and no object exists

#### Scenario: Duplicate key
- **WHEN** an object is created with a key the layer already has
- **THEN** the response is `409 conflict` and the existing object is unchanged

### Requirement: Shared maps and their moderation over the API
Question create and update SHALL accept `layer_from_answers: <code of a top-level geo question>`
instead of `layer_id`, creating or reusing that question's shared-map layer exactly as the editor
does (and refusing past 10 layers). `PATCH /surveys/{uuid}/layers/{id}/objects/{key}/status` with
`visible`, `pending` or `hidden` (scope `surveys:write`, role `editor`) SHALL moderate a mark of a
shared-map layer and rebuild it; on any other layer it SHALL answer `409 conflict`.

#### Scenario: Turn answers into a shared map
- **WHEN** an "Objects on the map" question is created with `layer_from_answers: "BENCH"` where BENCH is a point question
- **THEN** the question is bound to a layer with `source: "question"` and `source_question_code: "BENCH"`

#### Scenario: Hide a mark
- **WHEN** an editor sets a mark to `hidden`
- **THEN** the mark leaves the respondents' shared map at once
