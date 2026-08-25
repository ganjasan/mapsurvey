# reference-overlay-layers Delta Specification

## ADDED Requirements

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
