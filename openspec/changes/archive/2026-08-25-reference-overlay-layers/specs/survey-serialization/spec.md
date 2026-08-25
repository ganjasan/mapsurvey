# survey-serialization Delta Specification

## ADDED Requirements

### Requirement: Reference layers serialization
Survey export SHALL include a `layers` array on the survey object (name, color,
label_field, key_field, show_popups, position — ordered by position) and one
`layers/<position>.geojson` archive entry per layer, written from the stored text (no
filesystem paths). Section objects SHALL include `hidden_layers` as a list of
position-indexes into the `layers` array. Import SHALL recreate layers through the same
validation as interactive upload, remap position-indexes to the new layer IDs, treat a
missing or invalid `layers/` entry as a warning that skips that layer (never a hard
error), and accept archives without any `layers` key. Layer config coming from an
archive SHALL pass a whitelist cleaner (unknown keys dropped, color validated,
defaults applied).

#### Scenario: Layers round-trip
- **WHEN** a survey with two configured layers and a section hiding the second is exported and re-imported
- **THEN** the imported survey has both layers with identical config and the corresponding section hides the second layer

#### Scenario: Legacy archive imports cleanly
- **WHEN** a pre-change archive (no `layers` key, no `layers/` entries) is imported
- **THEN** the survey imports with zero layers and no warnings about layers

#### Scenario: Corrupt layer entry degrades to a warning
- **WHEN** `survey.json` lists a layer whose `layers/0.geojson` is missing or fails validation
- **THEN** the import succeeds without that layer and reports a warning naming it
