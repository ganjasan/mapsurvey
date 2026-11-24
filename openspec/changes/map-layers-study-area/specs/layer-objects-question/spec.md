## MODIFIED Requirements

### Requirement: The `layer_objects` question type
A question of type `layer_objects` ("Objects on the map") SHALL ask about each object of one
reference layer linked to the survey; its sub-questions are its body. It SHALL carry `min_objects`
(default 0) and `objects_search` (`auto`/`on`/`off`, default `auto`); it SHALL NOT carry a panel mode.
It SHALL be offered only on map-layout sections and SHALL NOT itself be a sub-question. Its
sub-questions SHALL use `parent_question_id` and SHALL exclude geo types and `layer_objects`.
Saving the question with a layer that is not placed on its section SHALL place the layer there
through the placement service; deleting the question SHALL NOT remove a placement. A question with
no sub-questions SHALL collect nothing (no answered state, no `min_objects` requirement, no progress
step) and the editor SHALL say that the layer already shows from the Map card and that sub-questions
ask about each object. A layer SHALL be asked about at most once per section.

#### Scenario: Create with a layer
- **WHEN** a creator adds an "Objects on the map" question and picks the layer "Остановки"
- **THEN** the question stores that layer, appears in the section list with the layer badge and count, and offers "Add Sub-question"

#### Scenario: Picking a layer not on the map places it
- **WHEN** the creator picks "MARTA bus stops", which is linked to the survey but placed on no section
- **THEN** saving the question places the layer on this section and the Map card lists it as "Asked in section N"

#### Scenario: Question without sub-questions
- **WHEN** an Objects question has no sub-questions
- **THEN** the section submits without any object answered, the form hides "Minimum objects" and shows the hint pointing at the Map card

#### Scenario: Same layer twice in a section
- **WHEN** the creator picks a layer already asked about by another Objects question of the section
- **THEN** the form refuses with "Already asked about in '<question name>'"

#### Scenario: Layer removed while asked about
- **WHEN** an owner tries to remove from the survey a layer an Objects question asks about
- **THEN** the removal is refused with a message naming the question and its section
