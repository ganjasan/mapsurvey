# survey-editor — delta for layers-by-question

## ADDED Requirements

### Requirement: Layers are put on a map by adding a question
The section form SHALL NOT offer a per-section reference-layer checklist. The Objects-on-
the-map question form SHALL be the one place a layer is put on a section's map; its layer
picker SHALL list the survey's layers, the "Respondents' marks on…" sources, and an
"Upload a new layer…" entry that runs the Survey-settings upload flow and selects the new
layer on success. The Survey-settings layer card SHALL name the sections a layer is shown
in.

#### Scenario: Show an uploaded layer on a section
- **WHEN** the creator adds an Objects question, picks "existing-dog-bins", saves with no sub-question
- **THEN** the section list shows the question with the layer badge, "14 objects" and "legend"/"list", and the preview map renders the layer

#### Scenario: Upload from the question form
- **WHEN** the creator chooses "Upload a new layer…" in the picker and uploads a GeoJSON
- **THEN** the layer is created in Survey settings and is selected in the picker without leaving the modal

#### Scenario: Section form on a map section
- **WHEN** the creator opens a map-layout section's settings
- **THEN** there is no "Reference layers" block; the layout field's help text says layers are added as Objects-on-the-map questions

## MODIFIED Requirements

### Requirement: Source geo questions are protected
The system SHALL refuse to delete a point, line or polygon question whose code is the
`source_question_code` of a `question` layer **that an Objects-on-the-map question of the
same survey header still shows**, with a message naming that question and its section.
Readers in other headers (the published version while a draft is edited) SHALL NOT block
the draft. A `question` layer no Objects question in any header shows is derived data with
no reader: deleting its source question SHALL delete the layer with it, and deleting the
last Objects question that shows a `question` layer SHALL delete the layer; while any
header still shows it the layer stays. Question codes are not editable in the editor; where an import remaps codes, the
layer's `source_question_code` SHALL follow the remap. The question form SHALL show a note
naming the layer(s) that read its answers. Deleting any question SHALL refresh the editor
preview.

#### Scenario: Source question cannot be deleted while shown
- **WHEN** the creator deletes `Q1` while an Objects question shows the layer sourced from `Q1`
- **THEN** the deletion is refused with a message naming that Objects question

#### Scenario: Last Objects question deleted
- **WHEN** the creator deletes the only Objects question showing the marks layer of `Q1`
- **THEN** the layer is deleted, the preview refreshes, and `Q1` can now be deleted

#### Scenario: Remapped code follows on import
- **WHEN** an archive whose `Q1` collides with an existing code is imported and `Q1` is remapped
- **THEN** the layer's `source_question_code` is the remapped code

#### Scenario: Published version still shows the layer
- **WHEN** the creator deletes `Q1` in a draft copy whose own Objects question is gone, while the published version's Objects question still shows the marks layer
- **THEN** the draft's `Q1` is deleted and the layer stays

### Requirement: Editor dialogs queue behind a closing dialog
When a dialog is requested while the editor dialog is still visible or fading out (a
409 answer to a request issued from a confirm's OK), the new dialog SHALL open after the
previous one has hidden, so no dialog is lost and no backdrop is left over the page.

#### Scenario: Refusal after a confirm
- **WHEN** the creator confirms a delete that the server refuses with 409
- **THEN** the refusal message opens as a dialog, and after closing it every button on the page responds again

### Requirement: The section list and the Live preview follow edits made inside the question modal
Creating or deleting a sub-question from inside the parent's modal SHALL re-render the
parent's row in the section list (out of band, scoped to the list so the modal's own rows
are untouched). An autosave SHALL notify the page so the Live preview re-renders, exactly
as an explicit save does. The modal's "Respondent sees" pane SHALL render the draft with
its picked layer — including a "Respondents' marks on…" source whose layer does not exist
yet — and with the collects/display-only state of the saved question.

#### Scenario: Row controls stay live after an autosave
- **WHEN** an autosave re-renders a question's row in the section list
- **THEN** the row's Edit, Duplicate and Delete controls still work without a reload, and a sub-question's autosave re-renders its parent's row with the child nested

#### Scenario: Sub-question added from the modal
- **WHEN** the creator adds a sub-question through the modal's "Add sub-question" and returns to the parent
- **THEN** the parent's row in the section list shows the new sub-question without a reload

#### Scenario: Autosave refreshes the preview
- **WHEN** the creator renames an Objects question and autosave reports "All changes saved"
- **THEN** the Live preview shows the new name

#### Scenario: Preview shows the layer's objects
- **WHEN** the modal previews an Objects question bound to a layer with objects
- **THEN** the "Respondent sees" pane lists the first objects with their categories as chips and, on a shared-map layer that shows them, 👍/👎 tallies — a picture of the respondent's panel

#### Scenario: Preview of an unsaved marks layer
- **WHEN** the creator picks "Respondents' marks on Q2" before saving
- **THEN** "Respondent sees" shows the shared-map block, not "not bound to a reference layer yet"

### Requirement: Closing the modal discards only an empty draft
A question created on type pick SHALL be deleted on modal close only when it has no name,
no layer and no sub-questions; a configured question SHALL be kept even without a name.
Picking a layer on an Objects question with an empty Name SHALL fill the Name from the
layer's name.

#### Scenario: Configured but unnamed
- **WHEN** the creator picks a layer, adds a 👍/👎 sub-question and closes the modal without typing a name
- **THEN** the question stays in the section, named after the layer
