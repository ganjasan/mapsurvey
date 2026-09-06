# layer-objects Specification

## Purpose
TBD - created by archiving change overlay-features. Update Purpose after archive.
## Requirements
### Requirement: A reference layer is a container of objects
A reference layer SHALL consist of `LayerObject` rows, each with a key unique within the
layer, a title, an optional category, a rich-text description, an optional link, a WGS84
geometry (point, line or polygon), an ordered set of attachments and the raw properties it
was imported with. The layer's GeoJSON SHALL be derived from its objects and rebuilt on
every object write; it SHALL NOT be an independently editable source.

#### Scenario: Object write rebuilds the layer GeoJSON
- **WHEN** an owner renames object `m-034` in a layer
- **THEN** the layer's served GeoJSON contains a feature with `_key = "m-034"` and the new `_title`, and the layer's ETag changes

#### Scenario: Keys are unique per layer
- **WHEN** an import would create a second object with key `m-034` in the same layer
- **THEN** the import reports the collision for that row and does not create a duplicate

#### Scenario: Raw properties survive
- **WHEN** a GeoJSON feature with properties `{"stroke": "#0a0", "custom": 7}` is imported
- **THEN** the object keeps both properties and the derived feature carries them alongside the reserved `_key`, `_title`, `_category`, `_has_content`, `_cover`

### Requirement: Object content is fetched per object, not shipped with the layer
The derived GeoJSON SHALL carry only list-level fields (`_key`, `_title`, `_category`,
`_has_content`, `_cover`). Description, link and attachments SHALL be served by
`GET /surveys/<uuid>/layers/<id>/objects/<key>/` under the same access rules and kill switch
as the layer endpoint, with the description passed through `coerce_creator_html`.

#### Scenario: Card endpoint is gated like the layer
- **WHEN** an anonymous request fetches an object card of an unpublished survey without a test link
- **THEN** the endpoint refuses exactly as the layer endpoint would

#### Scenario: Description is sanitized on the way out
- **WHEN** an object's stored description contains `<script>` (e.g. from an imported file)
- **THEN** the card payload contains no script element and the visible text is preserved

### Requirement: Attachments on objects
An object SHALL accept up to 10 attachments of kinds image, audio, document, video (uploaded
files, ≤ 25 MB each, MIME-sniffed) and embed (a YouTube or Vimeo URL). Files SHALL be stored
on the public media tier under random, non-guessable keys. The total attachment size per
layer SHALL NOT exceed 200 MB. The first image by position SHALL be the object's cover.
Embed URLs from other hosts SHALL be rejected.

#### Scenario: Photo upload becomes the cover
- **WHEN** an owner uploads `render.jpg` to an object with no images
- **THEN** the asset is stored under a `layer_assets/<uuid>.jpg` key, the object's `_cover` in the derived GeoJSON points at it, and the file is readable without authentication

#### Scenario: Oversized or spoofed file rejected
- **WHEN** an owner uploads a 30 MB file, or a `.jpg` whose bytes are not an image
- **THEN** the upload is refused with a human-readable reason and no asset row is created

#### Scenario: Embed host allow-list
- **WHEN** an owner adds `https://youtu.be/x8f2…` as an embed
- **THEN** it is stored as kind `embed`; adding `https://evil.example/v` is refused

#### Scenario: Per-object and per-layer caps
- **WHEN** an object already has 10 attachments, or the layer's attachments total 200 MB
- **THEN** a further upload is refused with a message naming the cap

### Requirement: Layers and objects belong to the canonical survey
Layers and their objects SHALL be owned by the canonical survey; draft copies and archived
versions SHALL read the canonical survey's layers through one resolver. Object edits SHALL be
visible on every version, including the published one, immediately.

#### Scenario: Draft copy sees the layers
- **WHEN** an owner creates a draft copy of a published survey with a 40-object layer
- **THEN** the draft's editor and preview show the same 40 objects, and no objects are copied

#### Scenario: Edit on a published survey is live
- **WHEN** an owner fixes an object title while the survey is published
- **THEN** the next respondent page load shows the new title, and the editor displays a banner stating that changes are visible immediately

### Requirement: Existing layers migrate feature-by-feature
Layers created before this change SHALL be split into objects by a data migration: key from
`key_field` when set and unique, else `f-<index>`; title from `label_field`, then `name`,
then the key; Multi-part geometries exploded into one object per part with `<key>-<n>`; raw
properties kept. The migration SHALL verify feature count and bounding box against the
original and keep the original string in `geojson_legacy` for one release.

#### Scenario: Zones layer migrates losslessly
- **WHEN** the migration runs on a 35-polygon layer with `key_field = zone_id`
- **THEN** 35 objects exist keyed by `zone_id`, the derived GeoJSON has 35 features with the same bbox, and `geojson_legacy` holds the original text

#### Scenario: Duplicate keys in a legacy file fall back
- **WHEN** a legacy layer's `key_field` values are not unique
- **THEN** keys are assigned as `f-<index>` and a migration log line names the layer

### Requirement: Derived GeoJSON respects the existing caps
The derived GeoJSON SHALL stay within FD-1's caps (10 MB, 5000 features per layer, 10 layers
per survey). Creating an object that would exceed a cap SHALL be refused with a human-readable
reason.

#### Scenario: Feature cap
- **WHEN** a layer already holds 5000 objects and the owner draws another
- **THEN** the create request is refused with a message naming the cap

