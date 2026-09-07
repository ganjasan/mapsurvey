# reference-overlay-layers — delta for layers-by-question

## MODIFIED Requirements

### Requirement: Layer visibility is controllable per section and by the respondent
A layer SHALL appear on a section's map if and only if a top-level "Objects on the map"
(`layer_objects`) question of that section binds it; layers SHALL render in the order of
those questions. Sections SHALL NOT carry a separate visibility list. The respondent SHALL
be able to toggle each visible layer via the Leaflet layers control, which SHALL appear
whenever at least one layer is on the map. Form-layout sections render no map and
therefore no layers.

#### Scenario: Layer shown through a question
- **WHEN** section A has an Objects question bound to "existing-dog-bins" and section B has none
- **THEN** the layer renders on A's map and not on B's

#### Scenario: Question removed
- **WHEN** the creator deletes the only question binding a layer in a section
- **THEN** the layer is gone from that section's map on the next render

#### Scenario: Respondent toggles a layer off
- **WHEN** the respondent unchecks the layer in the layers control
- **THEN** the overlay disappears; answer geometry is unaffected

### Requirement: The editor preview renders reference layers
The editor's Live preview SHALL render exactly the layers the previewed section's questions
bind, from the same metadata builder the respondent page uses, so the preview never shows a
layer the respondent will not see.

#### Scenario: Preview after adding a layer question
- **WHEN** the creator adds an Objects question bound to a layer and the preview refreshes
- **THEN** the layer appears on the preview map with its legend line in the panel
