## ADDED Requirements

### Requirement: A map block shows several questions as layers
A map block SHALL be able to show, beside its own question, up to three other map questions of the
report's workspace on the same map, each named by its survey and question code. The block's own
question SHALL be drawn on top. A layer SHALL be refused when it names a question that is not a map
question, a question of another workspace, the block's own question, or a question the block
already shows. A layer whose survey or question no longer exists SHALL be left out of the page. The
report file SHALL carry the layers, and a copy of the report onto another survey SHALL read that
survey in every layer.

#### Scenario: Adding a layer
- **WHEN** an editor adds another map question of the survey to a map block
- **THEN** the page payload carries that question as a second layer in a colour of its own

#### Scenario: Removing a layer
- **WHEN** the editor removes the layer
- **THEN** the block is a map of one layer again

#### Scenario: Not a map question
- **WHEN** a choice question, the block's own question or a question of another workspace is posted as a layer
- **THEN** no layer is added

#### Scenario: The next round
- **WHEN** a report with a map of two layers is copied onto a survey that has both questions
- **THEN** the copy's second layer names that survey

### Requirement: Each layer of a map is drawn with its own view and settings
Every layer of a map block SHALL have its own view (`heat`, `hotspots` for a point question,
`squares`, `marks`), colour, name in the legend, and settings of the view: for heat its spread and
strength; for hot spots how many are numbered (5, 10 or all), what counts as one place (60, 120 or
300 m), whether the places are listed under the map and whether shading is drawn under the numbers;
for squares automatic, finer or coarser cells; for marks their size and whether they are opaque.
Each layer SHALL be built from areas with at least K respondents unless its own "Use every mark"
switch is on, and a layer with the switch on SHALL be listed before publishing and need the
author's confirmation. Settings equal to the defaults SHALL not be stored.

#### Scenario: A layer drawn its own way
- **WHEN** the editor draws the second layer as hot spots of 300 m places in another colour and name
- **THEN** that layer carries its spots, colour and name, and the block's own layer is unchanged

#### Scenario: Marks of one layer
- **WHEN** "Use every mark" is switched on for the second layer only
- **THEN** that layer carries every mark, the first none, and publishing asks the author to confirm

#### Scenario: View settings
- **WHEN** the editor sets a wide spread and strength 5 for a heat layer
- **THEN** the payload carries them and the block stores only those two settings

### Requirement: A map of several layers has a legend
A map block of more than one layer SHALL show a legend under the map naming each layer in its
colour, unless the author switched the legend off; a layer drawn as hot spots with its list on SHALL
have its places listed under the layer's name. When the author lets readers switch layers, the
legend SHALL carry a box per layer that turns it off and on, whether or not the legend was switched
off.

#### Scenario: The legend
- **WHEN** a reader opens a report with a map of two layers
- **THEN** the page names both layers under the map

#### Scenario: Readers switch layers
- **WHEN** the author lets readers switch layers
- **THEN** each row of the legend has a box for its layer
