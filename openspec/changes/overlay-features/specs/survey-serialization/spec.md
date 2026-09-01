## MODIFIED Requirements

### Requirement: Reference layers serialization
Survey export SHALL include a `layers` array on the survey object (name, color,
label_field, key_field, show_popups, position — ordered by position), one
`layers/<position>.geojson` archive entry per layer holding the derived GeoJSON (features
keyed by `_key`), one `layers/<position>/objects.json` entry listing every object's key,
title, category, description, link, raw properties and attachment manifest (kind, title,
position, embed URL or archive path), and the attachment files under
`layers/<position>/assets/<uuid>.<ext>`. Section objects SHALL include `hidden_layers` as a
list of position-indexes into the `layers` array; `layer_objects` questions SHALL reference
their layer by the same position-index. Import SHALL recreate layers, then objects (through
the same validation as interactive import), then attachments (copying files into media
storage), remap position-indexes to the new layer IDs, treat a missing or invalid `layers/`
entry or asset file as a warning that skips that item (never a hard error), and accept
archives without any `layers` key or without `objects.json` (legacy archives: objects are
created from the GeoJSON as the migration would). Layer and object config coming from an
archive SHALL pass a whitelist cleaner (unknown keys dropped, color validated, description
sanitized, embed hosts validated, defaults applied).

#### Scenario: Layers round-trip
- **WHEN** a survey with two configured layers and a section hiding the second is exported and re-imported
- **THEN** the imported survey has both layers with identical config and the corresponding section hides the second layer

#### Scenario: Objects and attachments round-trip
- **WHEN** a layer with 10 objects, one carrying two images and an embed, is exported and re-imported
- **THEN** the imported layer has 10 objects with identical keys, titles, descriptions and links, the object has two image assets copied into storage and the same embed

#### Scenario: Legacy archive imports cleanly
- **WHEN** a pre-change archive (no `layers` key, no `layers/` entries) is imported
- **THEN** the survey imports with zero layers and no warnings about layers

#### Scenario: FD-1 archive without objects.json
- **WHEN** an archive from before this change carrying `layers/0.geojson` but no `objects.json` is imported
- **THEN** objects are created from the GeoJSON features with keys and titles derived as the migration derives them

#### Scenario: Question bound to a layer round-trips
- **WHEN** a `layer_objects` question bound to the second layer is exported and re-imported
- **THEN** the imported question is bound to the imported second layer

#### Scenario: Missing asset file is a warning
- **WHEN** an archive's manifest names `assets/abc.jpg` but the entry is absent
- **THEN** the object imports without that asset and the report lists it
