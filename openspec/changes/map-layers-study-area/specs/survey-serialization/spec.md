## REMOVED Requirements

### Requirement: Section layer visibility rides as questions
**Reason**: A section's layers are its placements now, not its Objects questions.
**Migration**: Import converts both legacy forms — `hidden_layers` lists and legend-only Objects
questions — into placements (requirement "Reference layers serialization").

## MODIFIED Requirements

### Requirement: Reference layers serialization
Survey export SHALL include a `layers` array on the survey object (name, color, style,
label_field, key_field, show_popups, source, source_question_code, show_tallies,
show_comments, approve_first, position — ordered by position, one entry per layer the survey
links or owns), and for `upload` layers one `layers/<position>.geojson` archive entry holding the
derived GeoJSON (features keyed by `_key`), one `layers/<position>/objects.json` entry listing every
object's key, title, category, description, link, raw properties and attachment manifest (kind,
title, position, embed URL or archive path), and the attachment files under
`layers/<position>/assets/<uuid>.<ext>`. `question` layers SHALL write no GeoJSON, objects or
assets. The survey object SHALL include a `placements` array (layer position-index, scope `all` or
`sections`, section references, order); `layer_objects` questions SHALL reference their layer by the
same position-index. Sections SHALL NOT carry `hidden_layers`. Import SHALL recreate layers as
workspace layer datasets linked to the imported survey, then objects (through the same validation as
interactive import), then attachments (copying files into media storage), then placements, remap
position-indexes to the new layer IDs, create `question` layers empty and downgrade one whose
`source_question_code` names no geo question to an empty `upload` layer with a report line, treat a
missing or invalid `layers/` entry or asset file as a warning that skips that item (never a hard
error), and accept archives without any `layers` key or without `objects.json` (legacy archives:
objects are created from the GeoJSON as the migration would). An archive without `placements`
SHALL be converted: a section's `hidden_layers` list (when present) places every other layer on that
section, and each legend-only Objects question (no sub-questions) becomes a placement of its layer on
its section and is not imported as a question. Layer and object config coming from an archive SHALL
pass a whitelist cleaner (unknown keys dropped, color validated, `style` normalised, description
sanitized, embed hosts validated, `source` restricted to the two values, defaults applied).

#### Scenario: Layers and placements round-trip
- **WHEN** a survey with two layers, the first placed on every section and the second on section 2 only, is exported and re-imported
- **THEN** the imported survey links both layers with identical config and has the same two placements

#### Scenario: Objects and attachments round-trip
- **WHEN** a layer with 10 objects, one carrying two images and an embed, is exported and re-imported
- **THEN** the imported layer has 10 objects with identical keys, titles, descriptions and links, the object has two image assets copied into storage and the same embed

#### Scenario: Legacy archive imports cleanly
- **WHEN** a pre-change archive (no `layers` key, no `layers/` entries) is imported
- **THEN** the survey imports with zero layers and no warnings about layers

#### Scenario: FD-1 archive without objects.json
- **WHEN** an archive from before this change carrying `layers/0.geojson` but no `objects.json` is imported
- **THEN** objects are created from the GeoJSON features with keys and titles derived as the migration derives them

#### Scenario: Archive with legend-only questions
- **WHEN** an archive from `layers-by-question` has a legend-only Objects question bound to "Study Area" in each map section
- **THEN** the imported survey places "Study Area" on those sections and has no such questions

#### Scenario: Archive with hidden_layers
- **WHEN** an older archive's section lists the second layer in `hidden_layers`
- **THEN** the imported survey places the first layer on that section and not the second

#### Scenario: Question bound to a layer round-trips
- **WHEN** a `layer_objects` question with sub-questions, asking about the second layer, is exported and re-imported
- **THEN** the imported question asks about the imported second layer

#### Scenario: Missing asset file is a warning
- **WHEN** an archive's manifest names `assets/abc.jpg` but the entry is absent
- **THEN** the object imports without that asset and the report lists it

#### Scenario: Question layer round-trips as config
- **WHEN** a survey with a `question` layer (source `Q1`, comments on) and its pair question is exported and re-imported
- **THEN** the imported layer has `source='question'`, `source_question_code='Q1'`, `show_comments=True`, zero objects, and the pair question is bound to it

#### Scenario: Dangling source code downgrades
- **WHEN** an archive's `question` layer names a code that matches no geo question in the archive
- **THEN** it imports as an empty `upload` layer and the report says so

#### Scenario: Style round-trips and is normalised
- **WHEN** a layer with a four-class rule is exported, its archive edited to `weight: 99` on one class, and re-imported
- **THEN** the imported layer has the rule with that class's weight clamped to 12 and everything else identical

## ADDED Requirements

### Requirement: The study area rides the archive
Survey export SHALL include a `study_area` object (GeoJSON geometry, source, place name, fog,
refuse_outside, message and its translations) when the survey has one. Import SHALL recreate it
through the study area service's validation; an invalid geometry SHALL be skipped with a report line,
never a hard error. The refused-marks counter SHALL NOT be exported.

#### Scenario: Study area round-trips
- **WHEN** a survey with a study area (fog on, refusal on, a German message) is exported and re-imported
- **THEN** the imported survey has the same polygon, flags and both messages

#### Scenario: Broken geometry in an archive
- **WHEN** an archive's `study_area.geometry` is a LineString
- **THEN** the survey imports without a study area and the report says why
