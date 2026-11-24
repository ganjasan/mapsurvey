# layer-objects-question Specification

## Purpose
TBD - created by archiving change overlay-features. Update Purpose after archive.
## Requirements
### Requirement: The `layer_objects` question type
A question of type `layer_objects` ("Objects on the map") SHALL bind to one reference layer
of the survey and SHALL be the only way a layer reaches a section's map. It SHALL carry
`min_objects` (default 0), `objects_search` (`auto`/`on`/`off`, default `auto`) and
`panel_mode` (`list`/`legend`, default `list`). It SHALL be offered only on map-layout
sections and SHALL NOT itself be a sub-question. Its sub-questions SHALL use
`parent_question_id` and SHALL exclude geo types and `layer_objects`. A question with no
sub-questions SHALL collect nothing: it contributes no answered state, no `min_objects`
requirement and no progress step. A layer SHALL be bound at most once per section.

#### Scenario: Create with a layer
- **WHEN** a creator adds an "Objects on the map" question and picks the layer "Остановки"
- **THEN** the question stores that layer, appears in the section list with the layer badge, count and panel mode, and offers "Add Sub-question"

#### Scenario: Display-only question
- **WHEN** an Objects question bound to "existing-dog-bins" has no sub-questions
- **THEN** the layer renders on the map with clickable object cards, the panel shows no counter, the section submits without any object answered, and the form hides "Minimum objects"

#### Scenario: Same layer twice in a section
- **WHEN** the creator picks a layer already bound by another Objects question of the section
- **THEN** the form refuses with "Already on this section's map as '<question name>'"

#### Scenario: Layer deleted while bound
- **WHEN** an owner tries to delete a layer bound to a `layer_objects` question
- **THEN** the deletion is refused with a message naming the question and its section

### Requirement: The respondent panel lists the layer's objects
With `panel_mode = list` the question SHALL render a list of the bound layer's objects
(cover thumbnail when present, title, category) built from the layer GeoJSON already loaded
for the map, with a search box and category chips shown when `objects_search` is `on`, or
`auto` and the layer has categories or more than 5 objects. Filtering SHALL narrow both the
list and the map (non-matching features dimmed). With `panel_mode = legend` the question
SHALL render one line instead: the layer's swatch or rule legend, its name, its object
count and an on/off toggle kept in sync with the layers control.

#### Scenario: Small layer hides search
- **WHEN** a layer has 3 objects, no categories, `objects_search = auto` and `panel_mode = list`
- **THEN** the list renders without a search box or chips

#### Scenario: Legend line
- **WHEN** a question has `panel_mode = legend` and its layer holds 14 objects
- **THEN** the panel shows one line with the swatch, the name and "14", and toggling it off hides the layer exactly as the layers control does

#### Scenario: Chip filter narrows list and map
- **WHEN** the respondent taps the "Парки" chip on a `list` question
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

### Requirement: Opening an object on a phone reveals the map
On a mobile viewport (the panel overlays the map), opening an object from the list SHALL
hide the panel before the popup opens and SHALL show it again when that popup closes.
Desktop behaviour SHALL be unchanged.

#### Scenario: Tap a mark in the list on a phone
- **WHEN** a respondent on a 390 px viewport taps a mark row
- **THEN** the panel slides away, the map flies to the mark and its popup is fully visible

#### Scenario: Close the popup
- **WHEN** the respondent closes that popup
- **THEN** the panel returns with the list

### Requirement: What other respondents see is set per sub-question
A sub-question of an Objects-on-the-map question SHALL carry `share_with_respondents`.
When on, other respondents SHALL see that sub-question's answers on the object: 👍/👎
counts for a `thumbs` sub-question (on the feature, in the list and in the card), comments
for a text sub-question (in the card). Sharing SHALL work for a layer of any source — an
uploaded layer's objects share exactly like respondents' marks; the layer's `show_tallies`
and `show_comments` are no longer read. The Objects form SHALL show the switch on each
shareable sub-question row ("Others see 👍/👎 counts" / "Others see comments") and the
sub-question form SHALL offer the same as a checkbox; the source settings of a marks layer
(label field, approve-first) SHALL sit under the layer picker and only for
"Respondents' marks on…".

#### Scenario: Uploaded layer shares counts
- **WHEN** an uploaded layer's Objects question has a 👍/👎 sub-question with sharing on, and two respondents voted 👍 on a bin
- **THEN** other respondents see "👍 2" on that bin, in the list and in its card

#### Scenario: Comments stay private until shared
- **WHEN** a text sub-question's sharing is off
- **THEN** the object card shows no comments and no comment count; turning it on shows them

### Requirement: One-tap sub-question presets
The Objects form SHALL offer chips that create a preset sub-question in one tap — 👍/👎
("Do you like it?", shared), Rating ("How would you rate it?", codes 1–5) and Comment
("Anything to add?") — beside "Other…", which opens the full form for any type. The
creator renames a preset like any sub-question.

#### Scenario: One-tap 👍/👎
- **WHEN** the creator taps the 👍/👎 chip
- **THEN** a shared thumbs sub-question "Do you like it?" exists and the modal returns to the parent with the new row and its switch

