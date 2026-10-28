## MODIFIED Requirements

### Requirement: Respondent map renders reference layers beneath answers
On map-layout sections, the respondent map SHALL render the survey's reference layers
in a dedicated pane below answer geometry. Feature styling SHALL follow the layer's
`style`: a rule class by attribute when the layer has a rule, else simplestyle
properties in the feature (`stroke`, `fill`, `stroke-width`, `marker-color`,
`stroke-opacity`, `fill-opacity`), else the base style with the layer colour; point
features SHALL render as circle markers, or as glyph markers when an icon is set, never
default markers. When a label field is set, features SHALL show a permanent centered label
with the property value HTML-escaped. Layers with a rule and the legend flag SHALL show a
legend under their name in the layers control. Layers SHALL persist across HTMX section
navigation without refetching.

#### Scenario: Zones visible under observation markers
- **WHEN** a volunteer places observation points on a section whose survey has a zones layer
- **THEN** the zone polygons render beneath the markers, styled with the layer color and labeled from the label field

#### Scenario: Self-styled plan wins over layer color
- **WHEN** a layer's features carry simplestyle properties (e.g. green lawn, orange playground) and the layer has no rule
- **THEN** each feature renders in its own colors and the layer color is unused

#### Scenario: Rule wins over file colours
- **WHEN** the same layer gets a categories rule on `use`
- **THEN** each feature renders in its class colour and the file's simplestyle is unused

#### Scenario: Label values are escaped
- **WHEN** a feature's label property contains `<img onerror=...>`
- **THEN** the label displays the literal text and no HTML executes

#### Scenario: Layers survive section navigation
- **WHEN** the respondent moves to the next section via HTMX
- **THEN** visible layers remain on the map without a new fetch of layer geometry

#### Scenario: Legend in the layers control
- **WHEN** a layer with a four-class rule is visible on the section
- **THEN** the layers control shows its name and four legend rows
