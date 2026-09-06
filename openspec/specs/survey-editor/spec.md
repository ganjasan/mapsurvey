## Purpose

WYSIWYG survey editor at `/editor/surveys/<uuid>/` — the in-app authoring surface for creating, configuring, and managing surveys (sections, questions, sub-questions, choices, translations, map positions, lifecycle transitions). Replaces the Django admin as the primary survey-construction tool for end users.
## Requirements
### Requirement: Survey creation
The system SHALL provide a form at `/editor/surveys/new/` that allows authenticated users to create a new survey. The form SHALL include fields for survey name, organization, available languages, visibility, redirect URL, and thanks HTML, and — when an LLM provider is configured — an optional AI brief panel (goal, audience, map target, use-case) with a "Generate draft" action alongside the manual "Create empty" action. A manual submission (the "Create empty" action, or any POST without an explicit action) SHALL create a SurveyHeader (with auto-generated UUID) and one default section (marked `is_head=True`), then redirect to the survey editor using the UUID — byte-identical to the pre-AI behavior. A "Generate draft" submission SHALL follow the asynchronous generation flow defined in the `ai-survey-generation` capability and, on success, redirect to the populated survey's editor. On the mobile create wizard (`MOBILE_EDITOR_NAV`, viewport <1024px) with `CREATE_STEER_AI` on, choosing the empty action on the goal step SHALL — after the empty-path intercept defined in `ai-survey-generation`, when it applies — submit the empty creation immediately using the current hidden map framing values and redirect to the editor, without presenting the map step; the draft path SHALL continue to present the map step unchanged. With `CREATE_STEER_AI` off, the wizard's empty path SHALL continue to the map step as before.

#### Scenario: Create a new survey
- **WHEN** an authenticated user submits the survey creation form with name "my_test_survey" using the manual action
- **THEN** a SurveyHeader with that name and auto-generated UUID is created, a default section with `is_head=True` is created, and the user is redirected to `/editor/surveys/<uuid>/`

#### Scenario: Duplicate survey name allowed
- **WHEN** a user submits the creation form with a name that already exists for another user's survey
- **THEN** the survey SHALL be created successfully (names are not globally unique)

#### Scenario: Unauthenticated access denied
- **WHEN** an unauthenticated user accesses `/editor/surveys/new/`
- **THEN** the system redirects to the login page

#### Scenario: Legacy POST without action falls back to manual creation
- **WHEN** a POST reaches the view without an `action` parameter
- **THEN** the manual creation path runs exactly as before the AI panel existed

#### Scenario: Generate draft action
- **WHEN** an authenticated editor submits the form with the "Generate draft" action, a filled brief, and a configured provider
- **THEN** generation is enqueued and the page enters the polling state defined in `ai-survey-generation`, ending on success at the populated survey's editor

#### Scenario: Wizard empty path skips the map step
- **WHEN** a creator on the mobile wizard with a blank goal taps "Skip and start from scratch" on the goal step
- **THEN** the empty survey is created with the default map framing from the hidden position fields and the creator lands in the editor without seeing the "Where?" step

#### Scenario: Wizard draft path keeps the map step
- **WHEN** a creator on the mobile wizard fills the goal and taps "✨ Draft my survey"
- **THEN** the map step is presented and the create action dispatches to the draft path, unchanged by this change

#### Scenario: Wizard empty path with flag off
- **WHEN** `CREATE_STEER_AI` is off and a creator on the mobile wizard taps "Skip and start from scratch"
- **THEN** the wizard continues to the map step, as before this change

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

Each user action that changes what the preview shows (opening the editor, switching sections, saving a section or question, changing the preview language) SHALL trigger exactly one preview document load — never a duplicate load of the same URL from a single action.

A preview refresh SHALL load the new document off-screen and swap it into view only once loaded; the previously rendered preview SHALL remain visible for the entire duration of the load. While a load is in flight, the preview panel SHALL show a loading indicator over the stale content; the indicator SHALL disappear when the new document is swapped in.

#### Scenario: Preview updates after adding a question
- **WHEN** the user adds a new question to a section
- **THEN** the preview iframe reloads and shows the newly added question

#### Scenario: Preview shows survey as respondents see it
- **WHEN** the preview iframe loads
- **THEN** it renders the section using the same `survey_section.html` template used for survey-taking, with form submission disabled

#### Scenario: Section switch issues a single preview load
- **WHEN** the user clicks a section in the left sidebar
- **THEN** the network log contains exactly one GET of that section's preview URL for this click

#### Scenario: Editor open issues a single preview load
- **WHEN** the editor page finishes its initial load, including the HTMX load of the first section's detail panel
- **THEN** the network log contains exactly one GET of the first section's preview URL

#### Scenario: Stale preview stays visible during a slow refresh
- **WHEN** a preview refresh is triggered and the server has not yet delivered the new document
- **THEN** the previously rendered preview remains visible (no blank iframe), overlaid with a loading indicator

#### Scenario: Loading indicator clears on completion
- **WHEN** the refreshed preview document finishes loading
- **THEN** the new content replaces the stale content and the loading indicator is no longer shown

#### Scenario: Rapid successive refreshes settle on the latest
- **WHEN** a second refresh is triggered while an earlier one is still loading
- **THEN** the preview ends up showing the most recently requested URL and the loading indicator clears after it loads

### Requirement: Dashboard integration
The system SHALL wire the "New Survey" button in `/editor/` to navigate to `/editor/surveys/new/`. The "Edit" link for each survey SHALL navigate to `/editor/surveys/<uuid>/`.

#### Scenario: New Survey button navigates to creation form
- **WHEN** the user clicks "New Survey" on the dashboard
- **THEN** the browser navigates to `/editor/surveys/new/`

#### Scenario: Edit link navigates to editor
- **WHEN** the user clicks "Edit" for a survey on the dashboard
- **THEN** the browser navigates to `/editor/surveys/<uuid>/`

### Requirement: Rating display style picker
The question modal SHALL include a "Display as" control offering three options — "Survey default" (`default`), "Compact scale" (`scale_strip`), "Labeled list" (`list_pips`) — the two visual styles with a small preview thumbnail each. The control SHALL be visible only while the selected input type is `rating`, and its value SHALL persist to `Question.display_style` on save.

#### Scenario: Picker appears for rating questions
- **WHEN** the user opens the question modal and selects input_type `rating`
- **THEN** the "Display as" control becomes visible with "Survey default" preselected for a new question

#### Scenario: Picker hidden for other types
- **WHEN** the user switches the modal's input_type from `rating` to `choice`
- **THEN** the "Display as" control is hidden and does not affect the saved question

#### Scenario: Choosing a style persists
- **WHEN** the user selects "Labeled list" and saves the question
- **THEN** the question's `display_style` is `list_pips` and only this question is modified

### Requirement: Modal preview reflects display style
The question modal's preview iframe SHALL render the rating question with the same markup as the respondent view, using the question's resolved display style. When the user switches the "Display as" picker, the preview SHALL update to the newly picked style immediately, without saving.

#### Scenario: Preview uses the new renderers
- **WHEN** the modal preview renders a rating question resolved to `scale_strip`
- **THEN** the preview shows the numbered scale strip, not the legacy pill buttons

#### Scenario: Preview follows the picker before saving
- **WHEN** the user switches the picker from "Compact scale" to "Labeled list" without saving
- **THEN** the preview re-renders as a labeled list

### Requirement: Survey style settings
The survey settings page SHALL include a "Style" section with the survey-wide default rating display style ("Compact scale" / "Labeled list"). Saving SHALL persist the value to `SurveyHeader.style_settings.rating_display_style`.

#### Scenario: Default style saved
- **WHEN** the user selects "Labeled list" in the settings Style section and saves
- **THEN** `style_settings.rating_display_style` is `list_pips` and rating questions with `display_style = "default"` render as labeled lists

#### Scenario: Settings page without explicit choice keeps prior behavior
- **WHEN** a survey has never configured the Style section
- **THEN** its effective default rating style is `scale_strip`

### Requirement: New-user redirect to survey creation
The `/editor/` dashboard SHALL redirect users whose active organization has zero
canonical, non-deleted surveys — and whose role permits creating surveys — to
`/editor/surveys/new/?welcome=1`. The redirect SHALL be suppressed by the query parameter
`dashboard=1`; the create page SHALL expose a "Skip to dashboard" escape link carrying
that parameter, and its Cancel link SHALL carry it as well so no redirect loop is
possible.

#### Scenario: Empty org lands on create page
- **WHEN** an editor-or-higher user with no surveys in the active org opens `/editor/`
- **THEN** they are redirected to `/editor/surveys/new/?welcome=1` and the page shows a "Skip to dashboard" link

#### Scenario: Explicit dashboard access
- **WHEN** the same user opens `/editor/?dashboard=1`
- **THEN** the dashboard renders (empty state) without redirecting

#### Scenario: Org with surveys unaffected
- **WHEN** a user whose active org has at least one canonical non-deleted survey opens `/editor/`
- **THEN** the dashboard renders as today with no redirect

#### Scenario: Viewer role not redirected
- **WHEN** a viewer-role user in a zero-survey org opens `/editor/`
- **THEN** the dashboard renders normally (the viewer cannot create surveys, so the create page would be a dead end)

### Requirement: Section layout setting
The section settings form SHALL offer the layout choice — "Map" (default) and "Form" —
persisted to `SurveySection.layout`. When "Form" is selected, the map-position fields
(start position, zoom, geolocation) SHALL be hidden in the form; their stored values are
preserved for a later switch back. Saving `layout = "form"` on a section that contains geo
questions SHALL be refused with a message naming those questions.

#### Scenario: Creator makes a welcome section
- **WHEN** the creator sets the head section's layout to "Form" and saves
- **THEN** the section persists `layout = "form"` and respondent preview renders it full-width

#### Scenario: Switch refused over geo questions
- **WHEN** the creator sets layout "Form" on a section with a point question and saves
- **THEN** the form re-renders with an error naming the point question and the section stays `layout = "map"`

### Requirement: Question type picker respects the section layout
In a section with `layout = "form"`, the question modal's type picker SHALL NOT offer the
geo group (`point`, `line`, `polygon`), and the server SHALL reject a geo `input_type`
submitted into such a section regardless of the picker.

#### Scenario: Geo group absent in a form section
- **WHEN** the creator opens the new-question modal inside a form-layout section
- **THEN** the "Map questions" group is not shown

#### Scenario: Server-side rejection
- **WHEN** a POST creates a `line` question in a form-layout section
- **THEN** the response is an error and no question is created

### Requirement: Display style picker for choice questions
The question form SHALL offer a display-style selector when the question's input_type is
`choice`, with the options "List" (stored as `default`) and "Dropdown with search"
(stored as `dropdown`). The server SHALL accept `dropdown` only when the question's
input_type is `choice`; for other types the submitted value SHALL be normalized per the
existing display-style validation.

#### Scenario: Creator switches a long choice question to dropdown
- **WHEN** the creator edits a choice question, selects "Dropdown with search", and saves
- **THEN** the question's `display_style` is persisted as `dropdown`

#### Scenario: Picker absent on non-applicable types
- **WHEN** the creator edits a text question
- **THEN** no choice display-style selector is rendered

#### Scenario: Only concrete styles get cards; default-ness is a badge
- **WHEN** the creator opens the style picker on any question type that has one
- **THEN** every card names a concrete rendering (choice: "List", "Dropdown with search";
  rating: "Compact scale", "Labeled list", "Stars") and no card is named "Survey default";
  the card matching the survey-wide default carries a corner "Default" ribbon

#### Scenario: Picking the badged card preserves inherit semantics
- **WHEN** the creator selects the ribbon-badged card and saves
- **THEN** the stored `display_style` is `default` (inherit), so a later change of the
  survey-wide style still re-styles the question

### Requirement: Reference layers card in Survey settings
Survey settings SHALL include a "Reference layers" card (after "Respondent map")
showing each layer as a card with color swatch, name, object count and attachment summary,
an "Open editor" action leading to the layer's object editor, an edit state exposing a
*Style* block (base: colour, opacity, line width, point size, point icon; a "Style by
attribute" switch with property picker, categories / graduated mode, an editable class
table with colour, width, icon and legend label per class, an "other" class, an
"Auto-fill from data" action and a "Show legend to respondents" switch, with a live
preview of the layer), label field, key field (both pickable from the objects' property
names) and the info-popups toggle, plus a delete action and a "New layer" action. A
`question` layer's card SHALL show a "source: answers" badge naming the geo question and
the "Objects on the map" question(s) using it, SHALL expose only name and the base style
in its edit state, SHALL offer no upload/draw actions, and its "Open editor" SHALL open the
object editor read-only. The card SHALL NOT create `question` layers — they are created
from the Objects-on-the-map question form. Layer operations SHALL save via dedicated
endpoints and reflect results without a page reload; a style that fails normalisation
SHALL be reported on the card with the reason. Deleting a layer bound to a `layer_objects`
question SHALL be refused with a message naming the question. The card SHALL be visible to
owners only and absent when the kill switch is off.

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
- **THEN** the card shows the badge, names both, offers name and base style, and no label/key/popup fields, rule editor or upload zone

#### Scenario: Auto-fill a categories rule
- **WHEN** the owner switches on "Style by attribute", picks `priority_class` and clicks Auto-fill
- **THEN** the table lists the four values with counts, distinct colours and widths, and saving stores the rule

#### Scenario: Style saves without a reload
- **WHEN** the owner changes the base opacity
- **THEN** the card preview updates and the status reads Saved

### Requirement: Per-section layer visibility checklist
The section form SHALL include a "Reference layers" checklist between "Layout" and
"Button label" listing every survey layer with its color swatch and feature count;
unchecking hides the layer on that section's map. The checklist SHALL NOT render on
form-layout sections, when the survey has no layers, or when the kill switch is off.
The server SHALL drop unknown layer IDs from the submitted list.

#### Scenario: Hide a layer on one section
- **WHEN** the creator unchecks "Study area boundary" on the observations section and saves
- **THEN** the section's `hidden_layers` contains that layer's ID and other sections are unaffected

#### Scenario: No checklist on a form section
- **WHEN** the creator edits a section with `layout = "form"`
- **THEN** no layer checklist is rendered

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

