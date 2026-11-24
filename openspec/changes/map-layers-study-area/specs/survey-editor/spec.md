## REMOVED Requirements

### Requirement: Layers are put on a map by adding a question
**Reason**: Showing a layer moves to its placement on the map (spec `map-layer-placement`); the
Objects-on-the-map question only asks about objects. 503 of 605 Objects questions existed only to
show a layer, and creators who uploaded a layer did not find the question.
**Migration**: The section's Map card in Build places layers (*+ Layer*, scope "every section, now
and later" or picked sections). Existing legend-only questions become placements in a data
migration.

## ADDED Requirements

### Requirement: The section form points at the Map card
A map-layout section's settings SHALL NOT carry a reference-layer list; the layout field's help text
SHALL say that layers and the study area are set in the section's Map card. The Objects-on-the-map
question form's layer picker SHALL list the layers linked to the survey (marking those not on this
section's map), the "Respondents' marks on…" sources and *Upload a new layer*, which runs the Map
card's upload and selects the new layer.

#### Scenario: Section form on a map section
- **WHEN** the creator opens a map-layout section's settings
- **THEN** there is no "Reference layers" block and the help text names the Map card

#### Scenario: Upload from the question form
- **WHEN** the creator chooses *Upload a new layer* in the picker and uploads a GeoJSON
- **THEN** the layer is linked and placed and is selected in the picker without leaving the modal
