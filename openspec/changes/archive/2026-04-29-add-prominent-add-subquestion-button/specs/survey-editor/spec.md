## MODIFIED Requirements

### Requirement: Sub-question management for geo questions
The system SHALL allow adding, editing, and deleting sub-questions for geo-type questions (point, line, polygon). Sub-questions SHALL have `parent_question_id` set to the geo question. The sub-question form SHALL support the same fields as regular questions.

The entry point for adding a sub-question SHALL be a prominent, full-width button labelled "+ Add Sub-question" with a `fa-plus` icon, rendered **inside** every geo-type question card directly **below** the sub-question list. The button SHALL always be visible on geo-type cards — including when the sub-question list is empty. The button SHALL match the visual style of the section-level "+ New Question" button (dashed-border, subdued, accent-on-hover), sized for the nested context.

When the survey is in a read-only state (status `published` or `closed`), the button SHALL be rendered as `disabled` and SHALL show the tooltip "Create a draft to edit", consistent with all other editor structural-edit affordances. There SHALL NOT be a separate icon-button affordance for adding sub-questions.

A sub-question SHALL NOT be a geo-type question itself. The sub-question form (used for both creation and for editing an existing sub-question) SHALL exclude `point`, `line`, and `polygon` from the `input_type` field's available choices. A POST that attempts to create or update a sub-question with `input_type` in `{point, line, polygon}` SHALL be rejected by form validation and SHALL NOT mutate the database. The same `input_type` field SHALL continue to offer all geo and non-geo options when the form is used to create or edit a top-level question.

#### Scenario: Add sub-question to a point question
- **WHEN** the user clicks "+ Add Sub-question" on a point-type question card and creates a choice sub-question
- **THEN** a Question is created with `parent_question_id` set to the point question, and it appears nested under the parent in the question list

#### Scenario: Sub-question button only on geo questions
- **WHEN** the question list shows a `text` question and a `point` question
- **THEN** only the `point` question card renders an "+ Add Sub-question" button; the `text` question card renders no such button

#### Scenario: Button visible when no sub-questions exist
- **WHEN** a `polygon` question has zero sub-questions
- **THEN** the "+ Add Sub-question" button is still rendered below the (empty) sub-question area of that question card

#### Scenario: Button visible below an existing sub-question list
- **WHEN** a `line` question already has two sub-questions
- **THEN** the "+ Add Sub-question" button is rendered below the sub-question list, in addition to the listed sub-questions

#### Scenario: Button disabled in read-only state
- **WHEN** the survey status is `published` and the editor renders a geo question card
- **THEN** the "+ Add Sub-question" button is rendered with the `disabled` attribute and the tooltip "Create a draft to edit"

#### Scenario: Legacy icon-button entry point removed
- **WHEN** the editor renders any geo question card
- **THEN** the q-actions row contains only the edit and delete icon buttons; no `fa-sitemap` icon button is present

#### Scenario: Sub-question creation form excludes geo input types
- **WHEN** the user opens the "New Sub-question" modal for a geo question
- **THEN** the `input_type` select offers no `point`, `line`, or `polygon` options (and continues to offer non-geo options such as `text`, `choice`, `number`, `image`)

#### Scenario: Sub-question creation rejects geo input types server-side
- **WHEN** a POST is sent to `editor_subquestion_create` with `input_type=point` (e.g. by a stale or crafted request)
- **THEN** no Question is created and the response re-renders the form with a validation error on `input_type`

#### Scenario: Sub-question edit form excludes geo input types
- **WHEN** the user opens the edit modal for an existing sub-question (a Question with `parent_question_id` set)
- **THEN** the `input_type` select offers no `point`, `line`, or `polygon` options

#### Scenario: Top-level question form keeps geo input types
- **WHEN** the user opens the create modal for a section, or the edit modal for a top-level question
- **THEN** the `input_type` select still offers `point`, `line`, and `polygon` alongside the non-geo options
