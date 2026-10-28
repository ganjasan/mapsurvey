# survey-editor — delta for fix-draft-question-body-loss

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
leaving a sub-question SHALL return to the parent's modal. Closing the modal SHALL delete the
draft and remove its list item only when the question is EMPTY — no name, no subtext text, no
layer selected and no sub-questions; markup that carries no text SHALL NOT count as subtext.
Closing the modal BEFORE a type is picked SHALL NOT discard what was typed: when Name or
Subtext carries anything, the close SHALL create the question with input type `text`, carrying
both values; with both empty it SHALL create nothing. The picker SHALL still open with no type
selected. A published or closed survey SHALL refuse the draft like any structural edit.

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

#### Scenario: Close an empty draft
- **WHEN** the creator closes the modal having typed nothing at all
- **THEN** the draft question is deleted and its card disappears

#### Scenario: Close a named question
- **WHEN** the creator names the question (autosave) and closes the modal
- **THEN** the question stays

#### Scenario: Close a Formatted Text block that has a body but no name
- **WHEN** the creator picks Formatted Text, writes the body into Content, leaves Name empty and closes the modal
- **THEN** the question stays with its body intact, because subtext is the block's whole content

#### Scenario: Close before picking a type, having typed a name
- **WHEN** the creator types "Where do you park?" into Name and closes the modal without picking a type
- **THEN** a text question named "Where do you park?" is in the section, and the creator can change its type there

#### Scenario: Close an untouched New question modal
- **WHEN** the creator opens "New question" and closes it having typed nothing
- **THEN** no question is created

#### Scenario: Close a draft whose subtext holds only empty markup
- **WHEN** the creator opens and clears the rich-text editor so the subtext value carries markup but no text, and closes the modal
- **THEN** the draft question is deleted, because markup without text is not content
