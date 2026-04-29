## Purpose

WYSIWYG survey editor at `/editor/surveys/<uuid>/` — the in-app authoring surface for creating, configuring, and managing surveys (sections, questions, sub-questions, choices, translations, map positions, lifecycle transitions). Replaces the Django admin as the primary survey-construction tool for end users.
## Requirements
### Requirement: Survey creation
The system SHALL provide a form at `/editor/surveys/new/` that allows authenticated users to create a new survey. The form SHALL include fields for survey name, organization, available languages, visibility, redirect URL, and thanks HTML. On successful creation, the system SHALL create a SurveyHeader (with auto-generated UUID) and one default section (marked `is_head=True`), then redirect to the survey editor using the UUID.

#### Scenario: Create a new survey
- **WHEN** an authenticated user submits the survey creation form with name "my_test_survey"
- **THEN** a SurveyHeader with that name and auto-generated UUID is created, a default section with `is_head=True` is created, and the user is redirected to `/editor/surveys/<uuid>/`

#### Scenario: Duplicate survey name allowed
- **WHEN** a user submits the creation form with a name that already exists for another user's survey
- **THEN** the survey SHALL be created successfully (names are not globally unique)

#### Scenario: Unauthenticated access denied
- **WHEN** an unauthenticated user accesses `/editor/surveys/new/`
- **THEN** the system redirects to the login page

### Requirement: Survey editor layout
The system SHALL render the survey editor at `/editor/surveys/<uuid>/` as a 3-column layout: a left sidebar listing sections, a center panel showing the selected section's details and questions, and a right panel showing a live preview iframe. The editor page SHALL load HTMX and SortableJS from CDN.

#### Scenario: Editor page loads with sections and questions
- **WHEN** an authenticated user navigates to `/editor/surveys/<uuid>/`
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
The system SHALL allow creating, editing, deleting, and duplicating sections within a survey. Duplicating a section SHALL produce a clone immediately after the source in the linked list (3-node splice), with a unique deduplicated `name`, a `title` ending with ` (copy)`, all questions and translations cloned, and `is_head=False`. Creating a section SHALL append it to the end of the linked list. Deleting a section SHALL re-link its neighbors. Editing SHALL support title, subheading, and code fields.

(All existing scenarios preserved; this requirement adds the duplicate action.)

#### Scenario: Duplicate a section
- **WHEN** the user clicks Duplicate on section B in linked list [A, B, C]
- **THEN** the linked list becomes [A, B, B', C] where B' has all of B's questions cloned with fresh codes and `B'.title = B.title + " (copy)"`.

### Requirement: Section reordering via drag-and-drop
The system SHALL allow reordering sections by dragging them in the sidebar. On drop, the system SHALL rebuild the entire linked list (next_section/prev_section/is_head) to match the new visual order within a database transaction.

#### Scenario: Drag section B above section A
- **WHEN** sections are ordered [A, B, C] and the user drags B above A
- **THEN** the linked list is rebuilt as [B, A, C] with B.is_head=True, B.next_section=A, A.prev_section=B, A.next_section=C, C.prev_section=A

#### Scenario: Reorder persists after page reload
- **WHEN** sections are reordered and the page is refreshed
- **THEN** the sidebar shows sections in the new order

### Requirement: Question CRUD
The system SHALL allow creating, editing, deleting, and duplicating questions within a section via the WYSIWYG editor. Duplicating a question SHALL produce a clone immediately after the source (sibling-insert) with a freshly generated `code`, a `name` ending with ` (copy)`, and all other fields preserved including `validation_settings` and `image` path reference. The form SHALL include fields for name, subtext, input_type, required, color, icon_class, and image. Creating a question SHALL assign it the next order_number in the section.

(All existing scenarios for create / edit / delete preserved from the canonical spec; this requirement adds the duplicate action.)

#### Scenario: Duplicate a text question
- **WHEN** the user clicks Duplicate on a text question with `name="Feedback"` at `order_number=1`
- **THEN** a new Question is created with a fresh `code`, `name="Feedback (copy)"`, `order_number=2`; pre-existing siblings shift down.

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
The system SHALL wire the "New Survey" button in `/editor/` to navigate to `/editor/surveys/new/`. The "Edit" link for each survey SHALL navigate to `/editor/surveys/<uuid>/`.

#### Scenario: New Survey button navigates to creation form
- **WHEN** the user clicks "New Survey" on the dashboard
- **THEN** the browser navigates to `/editor/surveys/new/`

#### Scenario: Edit link navigates to editor
- **WHEN** the user clicks "Edit" for a survey on the dashboard
- **THEN** the browser navigates to `/editor/surveys/<uuid>/`

### Requirement: Duplicate question
The system SHALL provide a Duplicate action on every question card in the WYSIWYG editor that creates a clone of the question immediately after the source within the same section. The clone SHALL have a freshly generated unique `code` (via `question_code_generator()`), a `name` ending with ` (copy)`, and copies of all other fields including `subtext`, `input_type`, `choices`, `required`, `validation_settings`, `color`, `icon_class`, `image` (path reference), and all `QuestionTranslation` rows. Sub-questions of the source SHALL be cloned recursively with their own fresh codes (no `(copy)` suffix on sub-question names). The action SHALL be blocked by `_check_structural_edit_allowed` when the survey status is `published` or `closed`.

#### Scenario: Duplicate a top-level question
- **WHEN** the user clicks the Duplicate button on a question with `name="Address"` and `order_number=2` (and there exists a sibling at `order_number=3`)
- **THEN** a new Question is created in the same section with a freshly generated unique `code`, `name="Address (copy)"`, and `order_number=3`. The previously-existing question at `order_number=3` is shifted to `order_number=4`. The new card appears immediately below the source in the questions list.

#### Scenario: Duplicate preserves validation_settings
- **WHEN** the user duplicates a question with `validation_settings={"min_value": 0, "max_value": 100}`
- **THEN** the cloned question has the identical `validation_settings` dict.

#### Scenario: Duplicate preserves translations
- **WHEN** the user duplicates a question with `QuestionTranslation` rows for `en` and `ru`
- **THEN** the cloned question has equivalent `QuestionTranslation` rows for `en` and `ru` with the original (untouched) `name` and `subtext` values.

#### Scenario: Duplicate question with sub-questions
- **WHEN** the user duplicates a `point`-type question that has 2 sub-questions
- **THEN** the new question has 2 sub-questions, each with a freshly generated `code` and a `parent_question_id` pointing to the new top-level question. Sub-question names do NOT receive a `(copy)` suffix.

#### Scenario: Duplicate blocked on published survey
- **WHEN** the user attempts to duplicate a question on a survey with `status="published"`
- **THEN** the system returns HTTP 403 with the standard "Create a draft to edit" message.

### Requirement: Duplicate section
The system SHALL provide a Duplicate action on every section card in the editor sidebar that creates a clone of the section in the same survey, inserted immediately after the source in the linked list. The clone SHALL have `is_head=False` regardless of the source's `is_head`, a `title` ending with ` (copy)`, a unique `name` (deduplicated by appending `_2`, `_3`, … if collision), and copies of `subheading`, `code`, `start_map_postion`, `start_map_zoom`, `use_geolocation`, `override_basemap`, all `SurveySectionTranslation` rows, and all top-level questions (with sub-questions cloned recursively, all questions getting fresh codes). The action SHALL be blocked when survey status is `published` or `closed`.

#### Scenario: Duplicate a middle section
- **WHEN** sections are linked-list ordered [A, B, C] and the user duplicates B
- **THEN** the linked list becomes [A, B, B', C] where B' has all of B's questions cloned with new codes, B'.title = B.title + " (copy)", B.next_section=B', B'.prev_section=B, B'.next_section=C, C.prev_section=B'

#### Scenario: Duplicate the head section
- **WHEN** the user duplicates the head section H
- **THEN** the clone H' has `is_head=False` and is inserted at position 2 (H stays as head); the linked list becomes [H, H', ...rest]

#### Scenario: Duplicate section deduplicates name
- **WHEN** the user duplicates a section with `name="demographics"` and another section in the survey already has `name="demographics_2"`
- **THEN** the clone gets `name="demographics_3"` (or the next available `_N` suffix)

### Requirement: Editor clipboard (copy)
The system SHALL provide a Copy action on every section card and question card that writes a clipboard entry to `localStorage` under key `editor_clipboard`. The entry SHALL be a JSON object: `{kind: "question"|"section", source_survey_uuid: <uuid>, source_id: <int>, label: <string>, copied_at: <iso-timestamp>}`. The clipboard SHALL be readable across all browser tabs of the same origin. Only one entry exists at a time — copying a new item overwrites the previous entry.

#### Scenario: Copy a question
- **WHEN** the user clicks Copy on a question with id=42 in survey uuid=`abc-123`
- **THEN** `localStorage.editor_clipboard` contains a JSON string with `kind="question"`, `source_survey_uuid="abc-123"`, `source_id=42`, `label=<question.name>`, and a current timestamp.

#### Scenario: Copy overrides previous clipboard
- **WHEN** the user copies a section after having already copied a question
- **THEN** `localStorage.editor_clipboard` contains the section entry; the question entry is gone.

### Requirement: Editor clipboard (paste — questions)
The system SHALL provide a Paste action that fetches the source question fresh from the server and clones it into the target context. Paste SHALL be available in three target contexts: (a) at the top-level of the currently-open section ("Paste question here"), (b) as a sub-question of a `point`/`line`/`polygon` question card ("Paste as sub-question"). The user SHALL have at least viewer permission on the source survey AND editor permission on the target survey. The clone SHALL have a freshly generated `code`, NO `(copy)` suffix on the name, and `order_number = max(target_section_orders) + 1` when pasted as top-level (or `max(siblings.order_number) + 1` when pasted as sub-question). When the source is a sub-question and the target is a section (top-level paste), the clone SHALL have `parent_question_id=None` (promoted to top-level). When the source is a top-level question and the target is a sub-question slot (under a geo parent), the clone SHALL have `parent_question_id=<target_parent>` and the source's own sub-questions SHALL NOT be cloned.

When the paste target is a sub-question slot, the system SHALL reject the request if the source question's `input_type` is in `('point', 'line', 'polygon')` — enforcing the rule that a sub-question cannot itself be a geo-type question (per "Sub-question management for geo questions" requirement). The "Paste as sub-question" button SHALL be hidden when the clipboard contains a geo-type source.

#### Scenario: Paste question into same survey, different section
- **WHEN** the user copies a question from section A and pastes into section B (same survey)
- **THEN** a clone is created in section B at the tail of the question list with a fresh `code` and the original name (no suffix); the source question in section A is unchanged.

#### Scenario: Paste question cross-survey
- **WHEN** the user copies a question from survey X (where they have viewer role) and pastes into survey Y (where they have editor role)
- **THEN** the question is cloned into the open section of Y with a fresh `code`; both surveys remain functional independently.

#### Scenario: Paste question without source viewer permission
- **WHEN** the user attempts to paste a question whose source survey is no longer accessible (revoked permission, deleted survey)
- **THEN** the system returns HTTP 404 and the frontend clears `localStorage.editor_clipboard` and shows an error toast.

#### Scenario: Paste sub-question into section promotes to top-level
- **WHEN** a sub-question (`parent_question_id` set, parent is a `point`-type question) is in the clipboard, and the user pastes into a section directly (not as a sub-question)
- **THEN** the cloned question has `parent_question_id=None` and appears at the top level of the target section.

#### Scenario: Paste regular question as sub-question
- **WHEN** the user pastes a regular `text`-type question (no `parent_question_id`) into a `polygon`-type question via "Paste as sub-question"
- **THEN** the cloned question has `parent_question_id=<polygon_question.id>` and appears in the polygon's sub-question list. If the source had its own sub-questions, those are NOT cloned.

#### Scenario: Paste geo question as sub-question rejected
- **WHEN** the user attempts to paste a `point`/`line`/`polygon` question as a sub-question of another geo question
- **THEN** the server returns HTTP 400 with a validation error; no Question is created. The frontend's "Paste as sub-question" button is hidden when the clipboard contains a geo source so the request would not normally be sent.

#### Scenario: Paste-as-subquestion button hidden for geo clipboard
- **WHEN** the clipboard contains a `point`-type question (`kind="question"`, `input_type="point"`)
- **THEN** the "Paste as sub-question" button is hidden on every `point`/`line`/`polygon` question card; the "Paste question here" top-level button remains visible.

#### Scenario: Paste blocked on published target
- **WHEN** the target survey has status `published`
- **THEN** paste returns HTTP 403 with "Create a draft to edit" message; the clipboard is preserved.

### Requirement: Editor clipboard (paste — sections)
The system SHALL provide a Paste action for sections accessible from the editor sidebar ("Paste section"). The user SHALL have at least viewer permission on the source survey AND editor permission on the target survey. The pasted section SHALL be inserted at the tail of the target survey's section linked list with `is_head=False` (or `is_head=True` if it becomes the only section, e.g., target had no sections). The clone SHALL have a fresh unique name (deduplicated within the target survey) and NO `(copy)` suffix on the title. All translations and questions are cloned per the question-paste rules.

#### Scenario: Paste section cross-survey
- **WHEN** the user copies a section from survey X and pastes into survey Y
- **THEN** the section is appended at the tail of Y's linked list; all questions and translations are cloned with new codes.

#### Scenario: Paste section into empty survey
- **WHEN** the user pastes a section into a survey with no sections
- **THEN** the cloned section has `is_head=True` and is the head of the survey.

### Requirement: Keyboard shortcuts
The system SHALL bind keyboard shortcuts in the editor when a `.question-item` or `.section-item` card is the active card (last clicked, marked with `data-active="true"`). The shortcuts SHALL be: `Ctrl/Cmd+D` triggers duplicate; `Ctrl/Cmd+C` writes the active card to the clipboard; `Ctrl/Cmd+V` pastes the clipboard into the active section (top-level paste). Browser-native Ctrl+C SHALL continue to work when there is a non-empty text selection (`window.getSelection()`). All shortcuts SHALL be disabled when the survey is read-only.

#### Scenario: Ctrl/Cmd+D on active question
- **WHEN** a question card has `data-active="true"` and the user presses Ctrl+D (or Cmd+D on Mac)
- **THEN** the browser bookmark dialog is suppressed and the duplicate endpoint is invoked for that question; the clone appears as a sibling.

#### Scenario: Ctrl/Cmd+C does not block text selection copy
- **WHEN** the user has selected text on the page and presses Ctrl+C (regardless of any active card)
- **THEN** the browser performs a normal text copy; `localStorage.editor_clipboard` is NOT modified.

#### Scenario: Ctrl/Cmd+V into active section
- **WHEN** a section card is active and `localStorage.editor_clipboard` has `kind="question"`
- **THEN** the question is pasted into the active section at the top level; iframe preview refreshes.

#### Scenario: Shortcuts disabled on published survey
- **WHEN** the survey status is `published` and the user presses Ctrl+D on a question
- **THEN** no duplicate occurs and the shortcut handler returns silently (or shows a "Create a draft to edit" toast).

### Requirement: Active card tracking
The system SHALL track the most recently clicked `.question-item` or `.section-item` card as the active card by setting `data-active="true"` on the element and removing it from siblings. After every HTMX swap (`htmx:afterSettle` event), the system SHALL re-apply `data-active="true"` to the same card if it is still in the DOM (matched by `data-question-id` or `data-section-id`). The active card SHALL receive a subtle visual outline via a CSS rule on `[data-active="true"]`.

#### Scenario: Click on a card sets active
- **WHEN** the user clicks anywhere inside a `.question-item` (other than a button)
- **THEN** that card has `data-active="true"` and all other `.question-item` and `.section-item` cards have it removed.

#### Scenario: Active state survives HTMX swap
- **WHEN** an HTMX swap re-renders a section's question list and the previously-active question is still present
- **THEN** the question card retains `data-active="true"` after the swap completes.

