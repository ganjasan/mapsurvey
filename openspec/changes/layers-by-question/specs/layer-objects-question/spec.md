# layer-objects-question — delta for layers-by-question

## MODIFIED Requirements

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

## ADDED Requirements

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
