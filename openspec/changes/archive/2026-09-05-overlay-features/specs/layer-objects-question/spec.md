## ADDED Requirements

### Requirement: The `layer_objects` question type
A question of type `layer_objects` ("Objects on the map") SHALL bind to one reference layer
of the survey and SHALL carry `min_objects` (default 0) and `objects_search`
(`auto`/`on`/`off`, default `auto`). It SHALL be offered only on map-layout sections and
SHALL NOT itself be a sub-question. Its sub-questions SHALL use `parent_question_id` and
SHALL exclude geo types and `layer_objects`.

#### Scenario: Create with a layer
- **WHEN** a creator adds an "Objects on the map" question and picks the layer "Остановки"
- **THEN** the question stores that layer, appears in the section list with the layer badge and count, and offers "Add Sub-question"

#### Scenario: Layer deleted while bound
- **WHEN** an owner tries to delete a layer bound to a `layer_objects` question
- **THEN** the deletion is refused with a message naming the question

### Requirement: The respondent panel lists the layer's objects
On the respondent page the question SHALL render a list of the bound layer's objects
(cover thumbnail when present, title, category) built from the layer GeoJSON already loaded
for the map, with a search box and category chips shown when `objects_search` is `on`, or
`auto` and the layer has categories or more than 5 objects. Filtering SHALL narrow both the
list and the map (non-matching features dimmed).

#### Scenario: Small layer hides search
- **WHEN** a layer has 3 objects, no categories, and `objects_search = auto`
- **THEN** the list renders without a search box or chips

#### Scenario: Chip filter narrows list and map
- **WHEN** the respondent taps the "Парки" chip
- **THEN** only park objects remain in the list and other features on the map are dimmed

### Requirement: Opening an object uses the map popup
Clicking a row or its feature SHALL fly the map to the object, highlight it and open the
same Leaflet popup respondent-placed features use, containing the object card (cover,
category, sanitized description, attachments, link) fetched from the object endpoint and
the question's sub-question form, with a ✓ control only. The popup SHALL be sized by the
existing popup sizing rule. Closing the popup by any means SHALL keep typed values.

#### Scenario: Row click opens the popup
- **WHEN** the respondent taps "Парк на Ленина 14" in the list
- **THEN** the map flies to that polygon, it is highlighted, and a popup opens with its card and the sub-question form

#### Scenario: Feature click opens the same popup
- **WHEN** the respondent taps the polygon on the map
- **THEN** the same popup opens and the matching row is highlighted in the list

#### Scenario: No delete or edit controls
- **WHEN** the popup of a layer object is open
- **THEN** it shows the ✓ control and no 🗑 or ✎ control

### Requirement: Answered state and counter
Objects with at least one non-empty sub-answer SHALL be marked answered in the list (tick,
muted) and on the map (badge), and the block header SHALL show "Answered N of M". A
respondent SHALL be able to reopen an answered object and change answers.

#### Scenario: Mark after answering
- **WHEN** the respondent rates an object and taps ✓
- **THEN** the row shows a tick, the feature shows the answered badge, and the counter increments

#### Scenario: Reopen and change
- **WHEN** the respondent reopens an answered object and changes the rating
- **THEN** the new value replaces the old one and the counter is unchanged

### Requirement: Minimum objects instead of required
The question SHALL NOT use the ordinary `required` flag. When `min_objects > 0`, moving
forward SHALL require answers on at least that many distinct objects and otherwise show the
existing inline required message naming the minimum; when `min_objects = 0` the section is
passable with no object answered.

#### Scenario: Minimum not met
- **WHEN** `min_objects = 1` and the respondent taps Next with no object answered
- **THEN** the inline message "Please answer about at least 1 object" appears and the section stays

#### Scenario: Minimum zero
- **WHEN** `min_objects = 0` and the respondent taps Next with nothing answered
- **THEN** the next section opens

### Requirement: Objects never intercept drawing
While a draw or crosshair mode of any geo question is active, layer object features SHALL
be non-interactive and rows SHALL not open popups; interactivity SHALL return when the mode
ends.

#### Scenario: Tap over an object while placing a point
- **WHEN** point placement is active and the respondent taps inside an object polygon
- **THEN** the answer point is placed and no object popup opens

### Requirement: Editor preview matches the respondent page
The editor's section preview SHALL render the list block and popups exactly as the
respondent page does.

#### Scenario: Preview shows the list
- **WHEN** a creator views a section containing a `layer_objects` question in the preview
- **THEN** the list, chips and popup-on-click behave as on the respondent page
