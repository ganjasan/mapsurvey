## MODIFIED Requirements

### Requirement: Reference layers card in Survey settings
Survey settings SHALL include a "Reference layers" card (after "Respondent map")
showing each layer as a card with color swatch, name, object count and attachment summary,
an "Open editor" action leading to the layer's object editor, an edit state exposing
color, label field, key field (both pickable from the objects' property names) and the
info-popups toggle, plus a delete action and a "New layer" action. A `question` layer's
card SHALL show a "source: answers" badge naming the geo question and the "Objects on the
map" question(s) using it, SHALL expose only name and colour in its edit state, SHALL offer
no upload/draw actions, and its "Open editor" SHALL open the object editor read-only. The
card SHALL NOT create `question` layers — they are created from the Objects-on-the-map
question form. Layer operations SHALL save via dedicated endpoints and reflect results
without a page reload. Deleting a layer bound to a `layer_objects` question SHALL be refused
with a message naming the question. The card SHALL be visible to owners only and absent
when the kill switch is off.

#### Scenario: Open the editor from the card
- **WHEN** the owner clicks "Open editor" on a layer card
- **THEN** the object editor for that layer opens

#### Scenario: New layer goes straight to the editor
- **WHEN** the owner clicks "New layer"
- **THEN** an empty layer is created and its object editor opens in the empty state

#### Scenario: Bound layer cannot be deleted
- **WHEN** the owner clicks delete on a layer bound to a `layer_objects` question
- **THEN** the card shows a message naming the question and the layer remains

#### Scenario: Question layer card points at the question
- **WHEN** the owner opens the card of a layer sourced from `Q1`, used by "Marks by other residents"
- **THEN** the card shows the badge, names both, offers name and colour, and no label/key/popup fields or upload zone

## ADDED Requirements

### Requirement: Objects on the map source picker
The "Objects on the map" question form's layer picker SHALL offer two groups: the survey's
layers, and "Respondents' marks on…" listing the top-level point, line and polygon
questions that have no `question` layer yet. Saving with a geo question picked SHALL create
that question's `question` layer (one per geo question; a later pick reuses it) and bind
the question to it. When the bound layer is question-sourced the form SHALL show and save
the layer's label sub-question (choice types first, with the note that without a label marks
are listed by number) and the *show tallies*, *show other people's comments*, *approve marks
before they appear* settings; these SHALL be edited nowhere else. The type SHALL be offered
when the survey has at least one layer or one geo question.

#### Scenario: Pick a geo question as the source
- **WHEN** the owner creates an Objects question, picks "Where do we need a bin?" under Respondents' marks, sets the label to "Why here?" and saves
- **THEN** a `question` layer for that question exists with that label and default settings, the new question is bound to it, and the geo question no longer appears under Respondents' marks

#### Scenario: Settings travel with the question form
- **WHEN** the owner edits the bound Objects question, ticks "approve marks before they appear" and saves
- **THEN** the layer's `approve_first` is true and the layer card shows no such field

#### Scenario: Type offered without any uploaded layer
- **WHEN** a survey has a point question and no reference layer
- **THEN** the type picker still offers "Objects on the map"

### Requirement: Question rows are created on type pick
"New question" SHALL open the type picker alone. Picking a type SHALL create the question
(empty name) and SHALL re-render the modal as that question's edit modal — autosave,
type-specific fields, and for parent-capable types the Sub-questions block — adding the
question to the section list without a reload. The Sub-questions block SHALL list the
children with edit and delete, and an "Add sub-question" that opens the sub-question form
inside the same modal; creating or leaving a sub-question SHALL return to the parent's
modal. Closing the modal while the name is still empty SHALL delete the draft and remove
its list item. A published or closed survey SHALL refuse the draft like any structural
edit.

#### Scenario: Pick a type
- **WHEN** the creator clicks "New question" and picks Point
- **THEN** a nameless point question exists, the modal shows its edit form with the Sub-questions block, and the section list has a new card

#### Scenario: Add a sub-question without leaving the modal
- **WHEN** the creator clicks "Add sub-question", fills a text sub-question and creates it
- **THEN** the modal shows the parent again with the child listed, and the section list card lists it too

#### Scenario: Close an unnamed draft
- **WHEN** the creator closes the modal before typing a name
- **THEN** the draft question is deleted and its card disappears

#### Scenario: Close a named question
- **WHEN** the creator typed a name (autosaved) and closes the modal
- **THEN** the question stays

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
