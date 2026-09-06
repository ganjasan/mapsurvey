# survey-editor — delta for fix-new-question-modal-layout

## MODIFIED Requirements

### Requirement: Question rows are created on type pick
"New question" SHALL open the question modal with the same shell as the edit modal — Name,
Subtext, the Input type picker and the "Respondent sees" column — with no type selected and
everything below the picker (type-scoped settings, Create button) hidden. Picking a type
SHALL create the question, carrying the Name and Subtext typed so far, and SHALL re-render
the modal as that question's edit modal — autosave, type-specific fields, and for
parent-capable types the Sub-questions block — adding the question to the section list
without a reload. The Sub-questions block SHALL list the children with edit and delete, and
an "Add sub-question" that opens the sub-question form inside the same modal; creating or
leaving a sub-question SHALL return to the parent's modal. Closing the modal while the name
is still empty SHALL delete the draft and remove its list item. A published or closed survey
SHALL refuse the draft like any structural edit.

#### Scenario: Pick a type
- **WHEN** the creator clicks "New question" and picks Point
- **THEN** a nameless point question exists, the modal shows its edit form with the Sub-questions block, and the section list has a new card

#### Scenario: Name typed before the type
- **WHEN** the creator types "Where do you live?" into Name, then picks Point
- **THEN** the created point question is named "Where do you live?", the modal carries no draft marker, and closing it keeps the question

#### Scenario: No layout jump on type pick
- **WHEN** the New question modal opens
- **THEN** Name, Subtext and the preview column are already on screen, so picking a type changes only the area below the picker

#### Scenario: Add a sub-question without leaving the modal
- **WHEN** the creator clicks "Add sub-question", fills a text sub-question and creates it
- **THEN** the modal shows the parent again with the child listed, and the section list card lists it too

#### Scenario: Close an unnamed draft
- **WHEN** the creator closes the modal before typing a name
- **THEN** the draft question is deleted and its card disappears

#### Scenario: Close a named question
- **WHEN** the creator names the question (autosave) and closes the modal
- **THEN** the question stays
