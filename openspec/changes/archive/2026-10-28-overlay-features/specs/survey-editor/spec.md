## MODIFIED Requirements

### Requirement: Sub-question management for geo questions
The system SHALL allow adding, editing, and deleting sub-questions for questions that put
objects on the map: geo-type questions (point, line, polygon) and `layer_objects`
questions. Sub-questions SHALL have `parent_question_id` set to the parent question. The
sub-question form SHALL support the same fields as regular questions.

The single entry point into the "New Sub-question" modal SHALL be the section list: a
prominent, full-width button labelled "+ Add Sub-question" with a `fa-plus` icon, rendered
**inside** every parent-capable question card directly **below** the sub-question list,
always visible including when the list is empty, styled like the section-level "+ New
Question" button, sized for the nested context. The question modal itself SHALL NOT carry a
Sub-questions section: a question being created has no id to hang sub-questions on, so a
modal section could only ever work for edits, and a control that appears on the second
open but not the first reads as broken.

When the survey is in a read-only state (status `published` or `closed`), the entry point
SHALL be rendered `disabled` with the tooltip "Create a draft to edit". There SHALL NOT be
a separate icon-button affordance for adding sub-questions.

A sub-question SHALL NOT be a geo-type question or a `layer_objects` question. The
sub-question form (creation and edit) SHALL exclude `point`, `line`, `polygon` and
`layer_objects` from `input_type`. A POST that attempts to create or update a sub-question
with one of those types SHALL be rejected by form validation and SHALL NOT mutate the
database. The same `input_type` field SHALL continue to offer all types when the form is
used for a top-level question.

#### Scenario: Add sub-question to a point question
- **WHEN** the user clicks "+ Add Sub-question" on a point-type question card and creates a choice sub-question
- **THEN** a Question is created with `parent_question_id` set to the point question, and it appears nested under the parent in the question list

#### Scenario: No sub-questions does not block
- **WHEN** the user creates a polygon question and saves it without any sub-question
- **THEN** the question is saved; the modal carries no Sub-questions section on create or on edit

#### Scenario: Sub-question button only on parent-capable questions
- **WHEN** the question list shows a `text` question, a `point` question and a `layer_objects` question
- **THEN** the `point` and `layer_objects` cards render an "+ Add Sub-question" button; the `text` card renders none

#### Scenario: Button visible when no sub-questions exist
- **WHEN** a `polygon` question has zero sub-questions
- **THEN** the "+ Add Sub-question" button is still rendered below the (empty) sub-question area of that question card

#### Scenario: Button visible below an existing sub-question list
- **WHEN** a `line` question already has two sub-questions
- **THEN** the "+ Add Sub-question" button is rendered below the sub-question list, in addition to the listed sub-questions

#### Scenario: Button disabled in read-only state
- **WHEN** the survey status is `published` and the editor renders a parent-capable question card
- **THEN** the "+ Add Sub-question" button is rendered with the `disabled` attribute and the tooltip "Create a draft to edit"

#### Scenario: Legacy icon-button entry point removed
- **WHEN** the editor renders any parent-capable question card
- **THEN** the q-actions row contains only the edit and delete icon buttons; no `fa-sitemap` icon button is present

#### Scenario: Sub-question creation form excludes parent types
- **WHEN** the user opens the "New Sub-question" modal for a geo or `layer_objects` question
- **THEN** the `input_type` select offers no `point`, `line`, `polygon` or `layer_objects` options (and continues to offer non-parent options such as `text`, `choice`, `rating`, `thumbs`, `number`, `image`)

#### Scenario: Sub-question creation rejects parent types server-side
- **WHEN** a POST is sent to `editor_subquestion_create` with `input_type=point` or `input_type=layer_objects`
- **THEN** no Question is created and the response re-renders the form with a validation error on `input_type`

#### Scenario: Sub-question edit form excludes parent types
- **WHEN** the user opens the edit modal for an existing sub-question
- **THEN** the `input_type` select offers no `point`, `line`, `polygon` or `layer_objects` options

#### Scenario: Top-level question form keeps parent types
- **WHEN** the user opens the create modal for a section, or the edit modal for a top-level question
- **THEN** the `input_type` select still offers `point`, `line`, `polygon` and `layer_objects` alongside the other options

### Requirement: Reference layers card in Survey settings
Survey settings SHALL include a "Reference layers" card (after "Respondent map")
showing each layer as a card with color swatch, name, object count and attachment summary,
an "Open editor" action leading to the layer's object editor, an edit state exposing
color, label field, key field (both pickable from the objects' property names) and the
info-popups toggle, plus a delete action and a "New layer" action. Layer operations SHALL
save via dedicated endpoints and reflect results without a page reload. Deleting a layer
bound to a `layer_objects` question SHALL be refused with a message naming the question.
The card SHALL be visible to owners only and absent when the kill switch is off.

#### Scenario: Open the editor from the card
- **WHEN** the owner clicks "Open editor" on a layer card
- **THEN** the object editor for that layer opens

#### Scenario: New layer goes straight to the editor
- **WHEN** the owner clicks "New layer"
- **THEN** an empty layer is created and its object editor opens in the empty state

#### Scenario: Bound layer cannot be deleted
- **WHEN** the owner clicks delete on a layer bound to a `layer_objects` question
- **THEN** the card shows a message naming the question and the layer remains

## ADDED Requirements

### Requirement: Objects on the map question form
The question modal for `layer_objects` SHALL offer a layer picker limited to the survey's
layers, a "respondent must answer on at least N objects" field (default 0) replacing the
`required` checkbox, and the search/chips mode (`auto`/`on`/`off`). Saving without a layer
SHALL fail validation. The modal preview SHALL show the list block as respondents see it.

#### Scenario: Layer required
- **WHEN** the creator saves an "Objects on the map" question without picking a layer
- **THEN** the form re-renders with a validation error on the layer field

#### Scenario: Minimum replaces required
- **WHEN** the creator opens the form for a `layer_objects` question
- **THEN** no `required` checkbox is rendered and the minimum-objects field is
