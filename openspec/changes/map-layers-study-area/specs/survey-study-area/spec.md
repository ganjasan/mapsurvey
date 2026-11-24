## ADDED Requirements

### Requirement: A survey has at most one study area, and it is not a layer
A survey SHALL be able to carry one study area: a polygon or multipolygon in WGS 84 owned by the
canonical survey and read by its draft copies and versions. The study area SHALL NOT be a reference
layer, SHALL NOT count toward the layer cap and SHALL NOT appear in the layer list or in Data. It
SHALL apply to every map section. Its geometry SHALL be simplified to at most 2,000 vertices on save.
Edits SHALL apply in place on a published survey and SHALL be available to the `editor` role and
above.

#### Scenario: Study area on a survey with layers
- **WHEN** a survey has ten reference layers and the creator sets a study area
- **THEN** the study area saves and the layer cap is not reached

#### Scenario: Every map section
- **WHEN** a survey with a study area has three map sections and a form section
- **THEN** the area applies to the three map sections and the form section renders no map

### Requirement: The study area is set from a place name and edited on the map
The study area editor SHALL accept a place name and offer up to five matching OpenStreetMap
boundaries (name, type, size), looked up server-side, cached, rate-limited per user and never from a
respondent page. A result whose OpenStreetMap geometry is a line (a street, a river, a rail line)
SHALL be offered as a corridor: the line buffered by a width the creator picks (50, 100 or 200 m,
default 100 m), computed server-side. A point-only result SHALL be offered as a rectangle around the
point (its OpenStreetMap bounding box when that is larger than 100 m across, otherwise 500 × 500 m),
labelled as having no boundary in OpenStreetMap; *Draw it* SHALL stay available. The chosen boundary SHALL open in vertex editing (move, add, remove points)
and SHALL be saved only when the creator confirms. Uploading a file (through the Data import),
using a polygon layer of the survey and drawing from scratch SHALL be secondary sources. The editor
SHALL credit OpenStreetMap contributors.

#### Scenario: A neighbourhood by name
- **WHEN** the creator types "Midtown, Atlanta", picks the neighbourhood result, moves six vertices and confirms
- **THEN** the survey's study area is the edited polygon with source `place` and the place name kept

#### Scenario: A street becomes a corridor
- **WHEN** the creator types "North Highland Avenue, Atlanta", picks the street result and the 100 m width
- **THEN** the editor opens a polygon 100 m either side of the street's line in vertex editing, and saving it gives a study area with source `place`

#### Scenario: Corridor width changed before saving
- **WHEN** the creator switches the corridor width from 100 m to 50 m before confirming
- **THEN** the polygon in the editor is rebuilt at 50 m and nothing is saved yet

#### Scenario: No boundary in OpenStreetMap
- **WHEN** the lookup returns only a point result for "Elm Park estate"
- **THEN** the editor says OpenStreetMap has no boundary for it and opens a rectangle around the point in vertex editing, with *Draw it* still offered

#### Scenario: Lookup unavailable
- **WHEN** the boundary service does not answer
- **THEN** the editor says it could not reach OpenStreetMap and offers upload and drawing; nothing is saved

#### Scenario: From an uploaded boundary
- **WHEN** the creator uploads a GeoJSON polygon in a State Plane coordinate system as the study area
- **THEN** it is reprojected to WGS 84 and becomes the study area with source `upload`, and no layer is created

### Requirement: The respondent map opens on the study area with fog outside
On a map section of a survey with a study area, the respondent map SHALL open on the area — keeping
the section's own start position only when that position lies inside the area — and SHALL draw the
area's outline. When fog is on (the default), everything outside the area SHALL be covered by a
near-opaque fog above the basemap and below reference layers and answers. The editor preview SHALL
render the same.

#### Scenario: Fog outside
- **WHEN** a respondent opens a map section of a survey whose study area has fog on
- **THEN** the map fits the area, the outside is fogged and the area is drawn in full colour

#### Scenario: Fog off
- **WHEN** fog is off
- **THEN** the outline is drawn and the outside map stays as it is

### Requirement: Map answers outside the study area can be refused
A creator SHALL be able to turn on "Map answers outside the area: not allowed". While it is on, the
respondent page SHALL NOT place a point, line or polygon outside the area and SHALL show the study
area's message saying why; spray dots outside the area SHALL be dropped as they are painted. The
section POST SHALL refuse the same geometries on the server: a point SHALL lie within the area and a
line or polygon SHALL be covered by the area widened by 5 metres; a refused geometry SHALL be skipped
(never a server error), logged with its question code and counted on the study area; a spray cloud
SHALL be clipped to the area. Answers about layer objects SHALL NOT be checked. Turning the rule on
SHALL NOT change answers already stored.

#### Scenario: Tap in the fog
- **WHEN** the rule is on and a respondent taps outside the area to place a point
- **THEN** no point is placed and the message "The study covers Elm Street between 10th St and North Ave." is shown

#### Scenario: Scripted mark outside
- **WHEN** a client posts a section with one point inside and one outside the area while the rule is on
- **THEN** the inside point is stored, the outside one is not, the response is the normal next page, and the refused count grows by one

#### Scenario: Line along the boundary
- **WHEN** a respondent draws a line that runs 3 metres outside the boundary for part of its length
- **THEN** the line is accepted

#### Scenario: Rule off
- **WHEN** the rule is off
- **THEN** marks outside the area are placed and stored as before

### Requirement: The study area message is translatable creator text
The study area's message SHALL be plain text, escaped on render, editable in the study area editor
and listed in the Translations tab as the occurrence `survey:study_area_message`; a respondent SHALL
read it in the survey language when a translation exists.

#### Scenario: Translated message
- **WHEN** the survey has a German translation of the message and a respondent takes the survey in German
- **THEN** the refusal shows the German message

### Requirement: The study area is writable through every surface
Setting, editing and clearing the study area SHALL go through one service
(`survey/services/study_area.py`) called by the editor, REST v1 and the MCP server with each
surface's role and Pro gates. Geometry from any surface SHALL be validated (polygonal, valid after
`ST_MakeValid`, within WGS 84 bounds) before anything is written. The creator event `study_area_set`
SHALL record the source, whether it was edited, fog and refusal; no event SHALL fire on respondent
pages.

#### Scenario: Set through MCP
- **WHEN** an agent calls `set_study_area` with a GeoJSON polygon and `refuse_outside: true`
- **THEN** the survey's study area is that polygon with the rule on and the editor shows it

#### Scenario: Not a polygon
- **WHEN** a client sends a LineString as the study area
- **THEN** the request is refused with a validation error and nothing changes

### Requirement: The study area outline shows on Responses and Reports maps
The Responses map SHALL draw the survey's study area as an outline (no fog, not clickable, under the
answers) and list it as "Study area" in its layers control, switched on. A Reports map block whose own
question belongs to a survey with a study area SHALL draw that outline on the canvas, the public and
embedded page, the PDF and the PNG; the block's panel SHALL carry a *Study area outline* switch, on by
default, stored only when switched off. The outline SHALL NOT change the block's frame, counts or
privacy checks, and a block SHALL NOT draw the study areas of its other layers' surveys.

#### Scenario: Outline on the Responses map
- **WHEN** the owner opens Responses for a survey with a study area
- **THEN** the map shows the area's outline under the answers without grey outside, and the layers control lists "Study area" switched on

#### Scenario: Outline in a report map block
- **WHEN** a report's map block shows a question of a survey with a study area and the report is exported to PDF
- **THEN** the canvas, the public page and the PDF image draw the outline and the hot spots are the same as without it

#### Scenario: Outline switched off for one block
- **WHEN** the author switches *Study area outline* off in a map block's panel
- **THEN** that block draws no outline, other blocks still do, and the block config stores `study_area: false`

#### Scenario: A survey without a study area
- **WHEN** a map block's question belongs to a survey with no study area
- **THEN** the panel shows no *Study area outline* switch and the payload carries no outline
