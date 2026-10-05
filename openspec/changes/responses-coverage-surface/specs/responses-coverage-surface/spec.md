## ADDED Requirements

### Requirement: Line and polygon answer layers can be turned into a coverage surface

On the Responses Map pane, the layer menu of a `features` layer whose geometry is LineString,
Polygon, MultiLineString or MultiPolygon SHALL offer *Create Coverage*; Point layers SHALL keep
*Create Heatmap* only. Creating coverage SHALL add a `coverage` slot to the `LayerManager`,
listed in the Layers panel directly under its source layer, drawn in its own pane, and the menu
SHALL show *Coverage exists* while the slot exists.

#### Scenario: Polygon layer offers coverage
- **WHEN** a creator opens the layer menu of a polygon question layer
- **THEN** the menu offers "Create Coverage" and, once created, a coverage row appears under the
  layer and the menu reads "Coverage exists"

#### Scenario: Point layer does not offer coverage
- **WHEN** a creator opens the layer menu of a point question layer
- **THEN** the menu offers "Create Heatmap" and no coverage entry

### Requirement: The surface shows the share of respondents covering each cell

A coverage surface SHALL draw, for every geographic cell in view, the share of respondents in
scope whose shape covers the cell: a polygon covers the cells inside it (holes excluded), a line
covers the cells within `corridorMeters` of it (default 20 m, never less than one cell). Each
respondent SHALL count once per cell whatever the number or size of their shapes. Cells SHALL be
world-anchored squares sized by the source layer's extent (longer side / 40, never finer than
20 m) unless the creator sets a cell size, and SHALL be rendered exactly as spray agreement cells
are: crisp cells in the layer's colour, opacity growing with the share, one canvas. A lone
respondent SHALL paint a flat surface at the minimum opacity. The surface SHALL be computed from
the same `L.SprayAgreementLayer` binning the spray clouds use, so spray rendering is unchanged.

#### Scenario: Overlap darkens
- **WHEN** 20 respondents drew polygons and a cell lies inside all 20
- **THEN** that cell is drawn at full opacity and a cell inside only one polygon at the minimum
  opacity

#### Scenario: Line corridor
- **WHEN** a route question's coverage has corridor 20 m and two respondents drew routes along
  the same street
- **THEN** the cells within 20 m of that street count both respondents and cells 100 m away
  count none

#### Scenario: One respondent, one vote
- **WHEN** one respondent drew three overlapping polygons over one spot
- **THEN** cells under all three count that respondent once

#### Scenario: Holes are not covered
- **WHEN** a respondent drew a polygon with a hole
- **THEN** cells inside the hole are not counted for that respondent

### Requirement: The surface follows the page's session scope and the layer's visibility

The coverage surface SHALL recount with the Map pane's session filter (table selection, issue
filters) exactly as heatmaps do, SHALL leave the map when its row is unchecked or its source has
no shapes in scope, and SHALL return when the row is checked again. Hiding the source layer
SHALL NOT hide the coverage (they are separate slots).

#### Scenario: Selection narrows the surface
- **WHEN** the creator selects 3 of 20 sessions in the table
- **THEN** the surface counts only those 3 respondents and its legend reads "of 3"

#### Scenario: Unchecked row removes the surface
- **WHEN** the coverage row's checkbox is cleared
- **THEN** no coverage canvas is on the map until it is checked again

### Requirement: Coverage rows have settings, a count and a remove button

A coverage row SHALL show a swatch in the layer's colour, a renamable label, an opacity control,
a settings button and a remove button, like a heatmap row. The settings popover SHALL offer the
cell size (10 m to 1 000 m) and, for line sources, the corridor width (5 m to 500 m); changes
SHALL redraw immediately. The row and the popover SHALL state "≤ N of M respondents" where N is
the highest count in any cell and M the respondents in scope. Removing the row SHALL remove the
slot, its pane and its canvas. The slot's position SHALL persist in the per-survey browser
order prefs like every other slot; the slot itself is not recreated on the next page load.

#### Scenario: Corridor edit redraws
- **WHEN** the creator moves the corridor slider from 20 m to 60 m on a line coverage
- **THEN** the surface redraws with the wider corridor at the current zoom and keeps it after a
  zoom change

#### Scenario: Count line
- **WHEN** 12 respondents are in scope and the most-covered cell has 7
- **THEN** the row reads "≤ 7 of 12 respondents"

#### Scenario: Remove
- **WHEN** the creator clicks the row's remove button
- **THEN** the row, the slot and the canvas are gone and the layer menu offers "Create Coverage"
  again

### Requirement: No draw into an unsized map

A coverage surface SHALL never read or write a canvas while the map container is 0×0 (the Map
pane starts hidden); creation SHALL wait for the map to have a size and every redraw SHALL return
early without a map or canvas, as the heat layer guard does.

#### Scenario: Created while the pane is hidden
- **WHEN** coverage is created before the Map pane has been opened
- **THEN** no exception is raised and the surface draws on the first redraw after the pane gets
  a size
