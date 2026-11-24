# survey-serialization — delta for layers-by-question

## ADDED Requirements

### Requirement: Section layer visibility rides as questions
Export SHALL NOT write a per-section `hidden_layers` list; a section's layers are the
`layer_objects` questions it exports. Import of an archive that still carries
`hidden_layers` on a section SHALL convert it: for every exported layer not listed there
and not already bound by a `layer_objects` question of that section, an Objects question
named after the layer with `panel_mode = legend` and `min_objects = 0` SHALL be appended
to the section, so the imported survey shows the same maps the archive did.

#### Scenario: Old archive with a ticked layer and no question
- **WHEN** an archive exported before this change has a layer, a map section whose `hidden_layers` is empty and no Objects question
- **THEN** the imported section has one Objects question bound to that layer in `legend` mode

#### Scenario: Old archive with the layer hidden
- **WHEN** the section's `hidden_layers` lists the layer
- **THEN** no question is created and the layer is not on that section's map

#### Scenario: New archive
- **WHEN** an archive exported after this change is imported
- **THEN** no conversion runs; the questions carry the bindings
