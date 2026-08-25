# survey-editor Delta Specification

## ADDED Requirements

### Requirement: Reference layers card in Survey settings
Survey settings SHALL include a "Reference layers" card (after "Respondent map")
showing each layer as a card with color swatch, name, feature count and size, an edit
state exposing color, label field, key field (both pickable from the file's property
names) and the info-popups toggle, plus a delete action and a GeoJSON upload drop-zone.
Layer operations SHALL save via dedicated endpoints and reflect results without a page
reload. The card SHALL be visible to owners only and absent when the kill switch is off.

#### Scenario: Upload from the settings card
- **WHEN** the owner drops `zones.geojson` on the card's upload zone
- **THEN** a layer card appears with feature count and size, and label/key dropdowns list the file's property names

#### Scenario: Invalid upload surfaces the reason
- **WHEN** the owner uploads a non-GeoJSON file
- **THEN** the card shows the server's human-readable error and no layer is created

### Requirement: Per-section layer visibility checklist
The section form SHALL include a "Reference layers" checklist between "Layout" and
"Button label" listing every survey layer with its color swatch and feature count;
unchecking hides the layer on that section's map. The checklist SHALL NOT render on
form-layout sections, when the survey has no layers, or when the kill switch is off.
The server SHALL drop unknown layer IDs from the submitted list.

#### Scenario: Hide a layer on one section
- **WHEN** the creator unchecks "Study area boundary" on the observations section and saves
- **THEN** the section's `hidden_layers` contains that layer's ID and other sections are unaffected

#### Scenario: No checklist on a form section
- **WHEN** the creator edits a section with `layout = "form"`
- **THEN** no layer checklist is rendered
