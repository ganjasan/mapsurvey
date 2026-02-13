## ADDED Requirements

### Requirement: Survey creation
The system SHALL provide a form at `/editor/surveys/new/` that allows authenticated users to create a new survey. The form SHALL include fields for survey name, organization, available languages, visibility, redirect URL, and thanks HTML. On successful creation, the system SHALL create a SurveyHeader and one default section (marked `is_head=True`), then redirect to the survey editor.

#### Scenario: Create a new survey
- **WHEN** an authenticated user submits the survey creation form with name "my_test_survey"
- **THEN** a SurveyHeader with that name is created, a default section with `is_head=True` is created, and the user is redirected to `/editor/surveys/my_test_survey/`

#### Scenario: Duplicate survey name rejected
- **WHEN** a user submits the creation form with a name that already exists
- **THEN** the form displays a validation error and does not create a survey

#### Scenario: Unauthenticated access denied
- **WHEN** an unauthenticated user accesses `/editor/surveys/new/`
- **THEN** the system redirects to the login page

### Requirement: Survey editor layout
The system SHALL render the survey editor at `/editor/surveys/<name>/` as a 3-column layout: a left sidebar listing sections, a center panel showing the selected section's details and questions, and a right panel showing a live preview iframe. The editor page SHALL load HTMX and SortableJS from CDN.

#### Scenario: Editor page loads with sections and questions
- **WHEN** an authenticated user navigates to `/editor/surveys/<name>/`
- **THEN** the left sidebar shows all sections in linked-list order, the center panel shows the first section's questions, and the right panel shows a live preview of that section

#### Scenario: Selecting a different section
- **WHEN** the user clicks a section in the sidebar
- **THEN** the center panel updates via HTMX to show that section's detail form and questions, and the preview iframe refreshes to show that section

### Requirement: Survey settings editing
The system SHALL provide a settings form (accessible from the editor) to edit SurveyHeader fields: name, organization, available_languages, visibility, redirect_url, and thanks_html.

#### Scenario: Update survey visibility
- **WHEN** the user changes visibility from "private" to "public" and saves
- **THEN** the SurveyHeader.visibility is updated to "public"

#### Scenario: Update available languages
- **WHEN** the user selects ["en", "ru"] as available languages and saves
- **THEN** the SurveyHeader.available_languages is updated to ["en", "ru"]

### Requirement: Section CRUD
The system SHALL allow creating, editing, and deleting sections within a survey. Creating a section SHALL append it to the end of the linked list. Deleting a section SHALL re-link its neighbors. Editing SHALL support title, subheading, and code fields.

#### Scenario: Create a new section
- **WHEN** the user clicks "New Section"
- **THEN** a new SurveySection is created, appended to the linked list (previous last section's `next_section` points to it, its `prev_section` points back), and the section appears in the sidebar

#### Scenario: Edit section title
- **WHEN** the user changes a section's title to "Demographics" and saves
- **THEN** the SurveySection.title is updated and the sidebar reflects the new title

#### Scenario: Delete a section
- **WHEN** the user deletes a section that has prev_section=A and next_section=C
- **THEN** the section is deleted, A.next_section is set to C, C.prev_section is set to A

#### Scenario: Delete the only section
- **WHEN** the user deletes the only section in a survey
- **THEN** the section is deleted and no linked-list fixup is needed

### Requirement: Section reordering via drag-and-drop
The system SHALL allow reordering sections by dragging them in the sidebar. On drop, the system SHALL rebuild the entire linked list (next_section/prev_section/is_head) to match the new visual order within a database transaction.

#### Scenario: Drag section B above section A
- **WHEN** sections are ordered [A, B, C] and the user drags B above A
- **THEN** the linked list is rebuilt as [B, A, C] with B.is_head=True, B.next_section=A, A.prev_section=B, A.next_section=C, C.prev_section=A

#### Scenario: Reorder persists after page reload
- **WHEN** sections are reordered and the page is refreshed
- **THEN** the sidebar shows sections in the new order

### Requirement: Question CRUD
The system SHALL allow creating, editing, and deleting questions within a section via a modal form. The form SHALL include fields for name, subtext, input_type, required, color, icon_class, and image. Creating a question SHALL assign it the next order_number in the section.

#### Scenario: Create a text question
- **WHEN** the user clicks "New Question", selects input_type "text", enters name "Your feedback", and saves
- **THEN** a Question is created in the current section with the given attributes and appears in the question list

#### Scenario: Edit a question's input type
- **WHEN** the user edits a question and changes input_type from "text" to "number"
- **THEN** the Question.input_type is updated and the question list item reflects the new type badge

#### Scenario: Delete a question
- **WHEN** the user deletes a question
- **THEN** the Question is deleted from the database and removed from the question list

### Requirement: Question reordering via drag-and-drop
The system SHALL allow reordering questions within a section by dragging. On drop, the system SHALL update `order_number` for all questions in the section to match the new visual order.

#### Scenario: Drag question 3 above question 1
- **WHEN** questions have order [Q1(0), Q2(1), Q3(2)] and the user drags Q3 above Q1
- **THEN** order_numbers are updated to Q3(0), Q1(1), Q2(2)

### Requirement: Choices editor for choice-based questions
The system SHALL display a dynamic choices editor when the question's input_type is choice, multichoice, range, or rating. The editor SHALL allow adding and removing choice rows. Each row SHALL have a code (integer) and name fields (one per available language for multilingual surveys, or a single field for single-language surveys). On save, choices SHALL be serialized to the `Question.choices` JSONField format: `[{"code": N, "name": {"en": "...", "ru": "..."}}]`.

#### Scenario: Add choices to a new choice question
- **WHEN** the user creates a question with input_type "choice", adds two choices with codes 1 ("Yes") and 2 ("No"), and saves
- **THEN** the Question.choices field is set to `[{"code": 1, "name": "Yes"}, {"code": 2, "name": "No"}]`

#### Scenario: Multilingual choices
- **WHEN** the survey has available_languages ["en", "ru"] and the user adds a choice with code 1, en name "Yes", ru name "Да"
- **THEN** the choice is stored as `{"code": 1, "name": {"en": "Yes", "ru": "Да"}}`

#### Scenario: Remove a choice
- **WHEN** the user removes the second choice from a question with 3 choices
- **THEN** the choices JSONField is updated to contain only the remaining 2 choices

#### Scenario: Choices editor hidden for non-choice types
- **WHEN** the user selects input_type "text" or "point"
- **THEN** the choices editor is not displayed

### Requirement: Sub-question management for geo questions
The system SHALL allow adding, editing, and deleting sub-questions for geo-type questions (point, line, polygon). Sub-questions SHALL have `parent_question_id` set to the geo question. The sub-question form SHALL support the same fields as regular questions.

#### Scenario: Add sub-question to a point question
- **WHEN** the user clicks "Add Sub-question" on a point-type question and creates a choice sub-question
- **THEN** a Question is created with parent_question_id set to the point question, and it appears nested under the parent in the question list

#### Scenario: Sub-question button only on geo questions
- **WHEN** the question list shows a "text" question and a "point" question
- **THEN** only the "point" question has an "Add Sub-question" button

### Requirement: Section map position picker
The system SHALL provide a Leaflet map picker for setting a section's start_map_position and start_map_zoom. The picker SHALL open in a modal, display a map centered at the section's current position, and allow the user to click to set a new position and adjust zoom.

#### Scenario: Set map position by clicking
- **WHEN** the user opens the map picker for a section and clicks on the map at coordinates (30.5, 60.0) with zoom level 14
- **THEN** the section's start_map_postion is updated to POINT(30.5 60.0) and start_map_zoom is updated to 14

#### Scenario: Default position for new sections
- **WHEN** a new section is created and the map picker is opened
- **THEN** the map is centered at the default position POINT(30.317 59.945) with zoom 12

### Requirement: Translation management
The system SHALL provide inline translation forms for sections (title, subheading) and questions (name, subtext) for each language in the survey's available_languages. Translations SHALL be saved to SurveySectionTranslation and QuestionTranslation models.

#### Scenario: Add Russian translation for a section title
- **WHEN** the survey has available_languages ["en", "ru"], the user enters a Russian title "Введение" for a section, and saves
- **THEN** a SurveySectionTranslation is created with language="ru" and title="Введение"

#### Scenario: No translation forms for single-language surveys
- **WHEN** the survey has empty available_languages
- **THEN** no translation form sections are displayed in the editor

### Requirement: Live inline preview
The system SHALL display a live preview of the currently selected section in the right panel of the editor. The preview SHALL render using the existing survey-taking templates in read-only mode (form submission disabled). The preview SHALL refresh after any edit operation.

#### Scenario: Preview updates after adding a question
- **WHEN** the user adds a new question to a section
- **THEN** the preview iframe reloads and shows the newly added question

#### Scenario: Preview shows survey as respondents see it
- **WHEN** the preview iframe loads
- **THEN** it renders the section using the same `survey_section.html` template used for survey-taking, with form submission disabled

### Requirement: Dashboard integration
The system SHALL wire the "New Survey" button in `/editor/` to navigate to `/editor/surveys/new/`. The "Edit" link for each survey SHALL navigate to `/editor/surveys/<name>/`.

#### Scenario: New Survey button navigates to creation form
- **WHEN** the user clicks "New Survey" on the dashboard
- **THEN** the browser navigates to `/editor/surveys/new/`

#### Scenario: Edit link navigates to editor
- **WHEN** the user clicks "Edit" for survey "my_survey" on the dashboard
- **THEN** the browser navigates to `/editor/surveys/my_survey/`
