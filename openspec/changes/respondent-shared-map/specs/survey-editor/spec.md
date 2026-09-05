## MODIFIED Requirements

### Requirement: Reference layers card in Survey settings
Survey settings SHALL include a "Reference layers" card (after "Respondent map")
showing each layer as a card with color swatch, name, object count and attachment summary,
an "Open editor" action leading to the layer's object editor, an edit state exposing
color, label field, key field (both pickable from the objects' property names) and the
info-popups toggle, plus a delete action, a "New layer" action and a "New layer from
answers" action that asks for a geo question and creates a `question` layer. A `question`
layer's card SHALL show a "source: answers" badge naming the question, SHALL expose the
label sub-question (choice sub-questions listed first, with the note that without a label
marks are listed by number), *show tallies*, *show other people's comments* and *approve
marks before they appear* settings in its edit state, SHALL offer no upload/draw actions, and
its "Open editor" SHALL open the object editor read-only. Layer operations SHALL save via
dedicated endpoints and reflect results without a page reload. Deleting a layer bound to
a `layer_objects` question SHALL be refused with a message naming the question. The card
SHALL be visible to owners only and absent when the kill switch is off.

#### Scenario: Open the editor from the card
- **WHEN** the owner clicks "Open editor" on a layer card
- **THEN** the object editor for that layer opens

#### Scenario: New layer goes straight to the editor
- **WHEN** the owner clicks "New layer"
- **THEN** an empty layer is created and its object editor opens in the empty state

#### Scenario: Bound layer cannot be deleted
- **WHEN** the owner clicks delete on a layer bound to a `layer_objects` question
- **THEN** the card shows a message naming the question and the layer remains

#### Scenario: New layer from answers
- **WHEN** the owner clicks "New layer from answers" and picks the polygon question `Q3`
- **THEN** a `question` layer for `Q3` appears with the "source: answers" badge, default settings, and no upload zone

## ADDED Requirements

### Requirement: Source geo questions are protected
The system SHALL refuse to delete a point, line or polygon question whose code is the
`source_question_code` of a `question` layer, with a message naming the layer. Question
codes are not editable in the editor; where an import remaps codes, the layer's
`source_question_code` SHALL follow the remap. The question form SHALL show a note naming
the layer(s) that read its answers.

#### Scenario: Source question cannot be deleted
- **WHEN** the creator deletes `Q1` while a `question` layer names `Q1`
- **THEN** the deletion is refused with a message naming the layer

#### Scenario: Remapped code follows on import
- **WHEN** an archive whose `Q1` collides with an existing code is imported and `Q1` is remapped
- **THEN** the imported layer's `source_question_code` is the remapped code
