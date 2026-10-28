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

#### Scenario: Requested destination survives the login redirect
- **WHEN** an unauthenticated user requests any survey-scoped editor URL and is redirected to the login page
- **THEN** the redirect SHALL carry the requested path as the `next` parameter, so that signing in returns the user to that URL rather than to the dashboard

### Requirement: Survey editor layout
The system SHALL render the survey editor at `/editor/surveys/<uuid>/` as a 3-column layout: a left sidebar with a pinned "Survey settings" entry above a list of sections, a center panel showing either the selected section's details and questions or the settings panel, and a right panel showing a live preview iframe. The editor page SHALL load HTMX and SortableJS from CDN.

#### Scenario: Editor page loads with sections and questions
- **WHEN** an authenticated user navigates to `/editor/surveys/<uuid>/`
- **THEN** the left sidebar shows the pinned "Survey settings" entry followed by all sections in linked-list order, the center panel shows the first section's questions, and the right panel shows a live preview of that section

#### Scenario: Selecting a different section
- **WHEN** the user clicks a section in the sidebar
- **THEN** the center panel updates via HTMX to show that section's detail form and questions, and the preview iframe refreshes to show that section

### Requirement: Survey settings editing
The system SHALL provide a settings form (accessible from the editor) to edit SurveyHeader fields: name, organization, available_languages, visibility, redirect_url, and thanks_html.

`redirect_url` SHALL be presented as a choice labelled "After the last page" with two options: "Show the thank-you page" (stored as `"#"`, the default) and "Open a web address". The address input SHALL be shown only when "Open a web address" is chosen, SHALL never be pre-filled with `"#"`, and SHALL carry a help text with an example address. On save the address SHALL be trimmed; a leading `"#"` in front of `http://`/`https://` SHALL be dropped; a value starting with `www.` SHALL get `https://` prepended; the scheme SHALL be lowercased. The result SHALL be accepted only if it is a valid absolute `http://` or `https://` URL; otherwise the form SHALL be invalid with an error on the address field that shows an example. "Open a web address" with an empty address SHALL save as `"#"` without an error.

#### Scenario: Update survey visibility
- **WHEN** the user changes visibility from "private" to "public" and saves
- **THEN** the SurveyHeader.visibility is updated to "public"

#### Scenario: Update available languages
- **WHEN** the user selects ["en", "ru"] as available languages and saves
- **THEN** the SurveyHeader.available_languages is updated to ["en", "ru"]

#### Scenario: Default survey shows the thank-you option
- **WHEN** the owner opens Survey settings on a survey whose `redirect_url` is `"#"`
- **THEN** "Show the thank-you page" is selected and the address input is hidden and empty

#### Scenario: Survey with a link shows the address option
- **WHEN** the owner opens Survey settings on a survey whose `redirect_url` is `"https://example.com/x"`
- **THEN** "Open a web address" is selected and the address input contains `"https://example.com/x"`

#### Scenario: A valid address is saved
- **WHEN** the owner chooses "Open a web address", enters `"https://www.example.org/project"` and saves
- **THEN** SurveyHeader.redirect_url is `"https://www.example.org/project"`

#### Scenario: A pasted anchor in front of the address is dropped
- **WHEN** the owner enters `"#https://www.example.org/project"` and saves
- **THEN** SurveyHeader.redirect_url is `"https://www.example.org/project"`

#### Scenario: A bare www address gets a scheme
- **WHEN** the owner enters `"www.example.org/project"` and saves
- **THEN** SurveyHeader.redirect_url is `"https://www.example.org/project"`

#### Scenario: An invalid address is refused
- **WHEN** the owner enters `"#projectname"`, `"/thanks"` or `"Thank you!"` and saves through autosave
- **THEN** the response is 400 with an error on the `redirect_url` field and SurveyHeader.redirect_url is unchanged

#### Scenario: Choosing the thank-you page clears the address
- **WHEN** the owner switches from "Open a web address" to "Show the thank-you page" and saves
- **THEN** SurveyHeader.redirect_url is `"#"`

#### Scenario: An empty address saves as the thank-you page
- **WHEN** the owner chooses "Open a web address" but leaves the address empty and saves
- **THEN** SurveyHeader.redirect_url is `"#"` and no error is shown

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
The system SHALL display a dynamic choices editor when the question's input_type is choice, multichoice, range, or rating. The editor SHALL allow adding and removing choice rows. Each row SHALL have a code (integer) and name fields (one per available language for multilingual surveys, or a single field for single-language surveys). On save, choices SHALL be serialized to the `Question.choices` JSONField format: `[{"code": N, "name": {"en": "...", "ru": "..."}}]`. For choice and multichoice questions each row SHALL also offer an "Other" checkbox that marks the row as the write-in option; checking one row SHALL uncheck any other, the checked row SHALL serialize with `"other": true`, the column SHALL not be offered for range and rating questions, and the server SHALL keep at most one flag per question. The choices editor script SHALL initialise for a star-rating question with no stored choices without error.

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

#### Scenario: Mark the write-in option
- **WHEN** the user checks "Other" on the row with code 4 and saves
- **THEN** that choice is stored as `{"code": 4, "name": "Other (specify)", "other": true}` and the other rows carry no flag

#### Scenario: Only one row can be the write-in option
- **WHEN** the user checks "Other" on code 2 while code 4 is checked
- **THEN** code 4 is unchecked, and a save carrying both flags anyway stores the flag on the first one only

#### Scenario: Reopening keeps the flag
- **WHEN** the user reopens the modal of a question whose code 4 carries `other: true`
- **THEN** the "Other" checkbox on that row is checked

#### Scenario: Star-rating modal initialises
- **WHEN** the modal opens for a rating question with display style "stars" and no stored choices
- **THEN** five star rows are added and the script completes without a ReferenceError

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
The system SHALL provide a Leaflet map picker for setting a section's start_map_position and start_map_zoom. The picker SHALL open in a wide modal and display the map centred on the section's own position, or on the survey's default position when the section has none. The position SHALL be the centre of the map and the zoom its zoom level: a fixed pin SHALL mark the centre, and dragging, zooming, choosing a place-search result and "My location" SHALL each move the map and thereby set the position. The picker SHALL NOT take a position from a click. Every settled move SHALL be saved automatically (debounced) through the section map-position endpoint, and a status indicator SHALL show saving, saved, or a failure with a retry; the modal SHALL have no Save button. The picker SHALL include the shared place search above the map. On viewports of 1024px and wider the map SHALL be at least 480px tall; narrower viewports keep the previous height.

An "Inherit position" checkbox SHALL be ticked when the section has no position of its own. Ticking it SHALL fly the map to the survey's default position, dim the pin, show that the section inherits, and save the cleared position at once. While it is ticked, movement of the map SHALL NOT be saved. Any creator gesture on the map — drag, scroll-wheel or pinch zoom, the zoom control, a place-search result, "My location" — SHALL untick it, after which the resulting centre is saved; programmatic moves SHALL NOT untick it. The section's geolocation flag and basemap override SHALL save on change through the same call.

#### Scenario: Set map position by dragging
- **WHEN** the user opens the picker for a section, unticks "Inherit position", drags the map so its centre is (60.0, 30.5) at zoom 14 and stops
- **THEN** the label shows those coordinates, the indicator shows "Saved", and the section's start_map_postion is POINT(30.5 60.0) with start_map_zoom 14 — without any click on the map or on a button

#### Scenario: Reopening shows the saved position
- **WHEN** the user closes the picker after the previous scenario and opens it again
- **THEN** the map opens centred on (60.0, 30.5) at zoom 14 with the pin on the centre and "Inherit position" unticked

#### Scenario: Dragging while inherit is ticked sets an own position
- **WHEN** the user opens the picker for a section with no position ("Inherit position" ticked) and drags the map
- **THEN** "Inherit position" is unticked by the drag, and the centre where the drag settles is saved as the section's own position

#### Scenario: Ticking inherit flies to the default and clears
- **WHEN** the user ticks "Inherit position" on a section that has its own position
- **THEN** the map flies to the survey's default position and zoom, the pin is dimmed, the label says the section inherits, the section's start_map_postion and start_map_zoom are cleared, and the fly itself saves nothing else

#### Scenario: Default position for new sections
- **WHEN** a new section is created and the map picker is opened
- **THEN** the map is centred on the survey's default position with "Inherit position" ticked

#### Scenario: Set map position by search
- **WHEN** the user opens the map picker for a section with "Inherit position" ticked, types "Tallinn" and chooses the result
- **THEN** "Inherit position" is unticked, the map centres on the result at the result's zoom, and the section's start_map_postion and start_map_zoom equal that centre and zoom

#### Scenario: Save fails
- **WHEN** a save request fails (network error, or the survey became read-only)
- **THEN** the indicator shows a failure and a tap on it retries; nothing is silently dropped

#### Scenario: Picker without a geocoder token
- **WHEN** `MAPBOX_ACCESS_TOKEN` is empty
- **THEN** the picker renders and saves by dragging exactly as above, with no search box

### Requirement: Translation management
The system SHALL show, in the section, question and group modals, a read-only Translations block
for each **non-primary** language in the survey's `available_languages` (every entry after the
first) with the stored translations of that entity (section: title, subheading, Next-button label;
question: name, subtext; group: title, description). The fields SHALL be disabled; each SHALL link
to the Translations tab opened on that language and scrolled to the entity's row, and the block
SHALL say that translations are edited there. Submitted `translation_<lang>_*` values SHALL be
ignored by the modal save paths; translations SHALL be written only through the Translations tab,
its CSV import, and the API/MCP services. No block SHALL be rendered for the primary language (its
content is edited through the base fields). When the survey has fewer than two available languages,
no Translations block SHALL be displayed. For surveys with two or more languages, base field labels
SHALL name the primary language (e.g. "Title (Português)").

#### Scenario: Open a translation from the question modal
- **WHEN** the survey has available_languages ["en", "ru"], a question has the Russian name "Введение", and the user opens the question modal
- **THEN** the Translations block shows "Введение" in a disabled field, and clicking it opens the Translations tab on Russian at that question's row

#### Scenario: Stale translation POST is ignored
- **WHEN** a form submission to the section or question endpoint includes `translation_ru_title` or `translation_pt_title`
- **THEN** no SurveySectionTranslation or QuestionTranslation row is created or updated by that request

#### Scenario: No translation block for single-language surveys
- **WHEN** the survey has available_languages ["es"] or empty available_languages
- **THEN** no Translations block is displayed in the editor

#### Scenario: No translation block for the primary language
- **WHEN** the survey has available_languages ["pt", "es", "en"] and the user opens a section or question form
- **THEN** read-only translation fields are rendered for "es" and "en" only, and the base title/name labels identify Portuguese as the language being edited

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
The system SHALL wire the "New Survey" button in `/editor/` by the creator's
`survey_start_default`: with no default it navigates to `/editor/surveys/start/`; with
`ai` to `/editor/surveys/new/`; with `blank` it is a POST form to
`/editor/surveys/new/blank/`. The dashboard's ⋯ menu SHALL offer "Start another way…"
linking to `/editor/surveys/start/`. The "Edit" link for each survey SHALL navigate to `/editor/surveys/<uuid>/`.

#### Scenario: New Survey button navigates to the start page
- **WHEN** a creator with no start default clicks "New Survey" on the dashboard
- **THEN** the browser navigates to `/editor/surveys/start/`

#### Scenario: New Survey button honours the AI default
- **WHEN** a creator with `survey_start_default='ai'` clicks "New Survey"
- **THEN** the browser navigates to `/editor/surveys/new/`

#### Scenario: New Survey button honours the blank default
- **WHEN** a creator with `survey_start_default='blank'` clicks "New Survey"
- **THEN** a POST creates a blank survey and the editor opens

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
that parameter, its Cancel link SHALL carry it as well, and the editor navbar's
"Dashboard" link SHALL carry it too, so no link reachable from the create page can
redirect back to it.

#### Scenario: Empty org lands on create page
- **WHEN** an editor-or-higher user with no surveys in the active org opens `/editor/`
- **THEN** they are redirected to `/editor/surveys/new/?welcome=1` and the page shows a "Skip to dashboard" link

#### Scenario: Explicit dashboard access
- **WHEN** the same user opens `/editor/?dashboard=1`
- **THEN** the dashboard renders (empty state) without redirecting

#### Scenario: Navbar Dashboard link does not loop
- **WHEN** the same user clicks "Dashboard" in the editor navbar on the create page
- **THEN** the dashboard renders (HTTP 200) instead of redirecting back to the create page

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
In a section with `layout = "form"`, the question modal's type picker SHALL show the map types
(`point`, `line`, `polygon`, `spraycan`, and `layer_objects` when it would otherwise be offered)
as DISABLED cards that cannot be picked, with one line under the group naming the reason and the
fix (switch the section's Layout to Map). The server SHALL reject a map `input_type` submitted
into such a section regardless of the picker.

#### Scenario: Map group disabled with a reason in a form section
- **WHEN** the creator opens the new-question modal inside a form-layout section
- **THEN** the "Map questions" group is shown with every card disabled
- **AND** the group says the section has no map and that switching its Layout to Map enables them
- **AND** clicking a disabled card creates nothing

#### Scenario: Map section unchanged
- **WHEN** the creator opens the new-question modal inside a map-layout section
- **THEN** the map cards are enabled and no reason line is shown

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

### Requirement: Survey default map position picker
The survey settings page and the in-editor settings panel SHALL provide a Leaflet map picker for the survey's start_map_position, start_map_zoom and use_geolocation, with the shared place search above the map. The position SHALL be the centre of the map and the zoom its zoom level: a fixed pin SHALL mark the centre, and dragging, zooming, choosing a search result and "My location" SHALL each move the map and thereby set the position; the picker SHALL NOT take a position from a click. Every settled move SHALL be saved automatically (debounced) through the survey map-position endpoint, the geolocation flag SHALL save on change, and a status indicator SHALL show saving, saved, or a failure with a retry; there SHALL be no Save button. On viewports of 1024px and wider the settings-page map SHALL be at least 460px tall and its section SHALL be allowed to exceed the 800px settings column; the in-editor panel map SHALL be at least 380px tall. Narrower viewports keep the previous heights.

#### Scenario: Move a survey to another city by search
- **WHEN** a creator opens survey settings for a survey positioned in Berlin, searches "Ülemiste, Tallinn" and chooses the result
- **THEN** the map centres on the result, the label shows the new coordinates, the indicator shows "Saved", and the survey's start_map_postion and start_map_zoom are the result's centre and zoom

#### Scenario: Move a survey by dragging
- **WHEN** a creator drags the settings-panel map so its centre is (59.437, 24.7536) at zoom 12 and stops
- **THEN** the survey's start_map_postion is POINT(24.7536 59.437) and start_map_zoom 12, with no button pressed

#### Scenario: Search box present on both settings surfaces
- **WHEN** the standalone settings page and the in-editor settings panel render with a Mapbox token configured
- **THEN** each contains one place-search input directly above its map picker

#### Scenario: Desktop map is not cramped
- **WHEN** the standalone settings page renders at 1280px width
- **THEN** the map picker is at least 460px tall and wider than the 800px settings column

### Requirement: Display as for choice and multichoice offers Icon grid
The question modal's "Display as" control SHALL be visible for the `choice`, `multichoice` and `rating` input types. For `choice` it SHALL offer List (the default), Dropdown and Icon grid. For `multichoice` it SHALL offer List (the default) and Icon grid. Each option SHALL be shown as a card with a small preview thumbnail. The picked value SHALL persist to `Question.display_style`. Switching it SHALL update the "Respondent sees" preview without saving.

#### Scenario: Multichoice shows two cards
- **WHEN** the creator selects input type `multichoice` in the question modal
- **THEN** "Display as" shows the List and Icon grid cards, with List selected for a new question

#### Scenario: Icon grid persists
- **WHEN** the creator picks Icon grid on a choice question and saves
- **THEN** the question's `display_style` is `icon_grid`

### Requirement: Choices table has Icon and Group columns for the icon grid
While Icon grid is the selected style, the choices table SHALL show two extra columns:

- an Icon column with the marker icon picker on every row, including rows added later;
- a Group column with a free-text input.

Under any other style both columns SHALL be hidden. Their values SHALL stay in the form, so switching back to Icon grid restores them. The values SHALL be saved as the choice's `icon` and `group`.

#### Scenario: Columns appear with the style
- **WHEN** the creator switches "Display as" from List to Icon grid
- **THEN** the Icon and Group columns appear in the choices table

#### Scenario: Picker on a new row
- **WHEN** the creator adds a choice row while Icon grid is selected and opens its icon picker
- **THEN** the picker opens with the catalog, and the picked value fills that row's Icon cell

#### Scenario: Switching away keeps the values
- **WHEN** the creator fills icons, switches to List and back to Icon grid without saving
- **THEN** the icons are still in their cells

### Requirement: Icon grid colour controls
While Icon grid is the selected style of a `choice` or `multichoice` question, the question modal SHALL show the question's **Color** field, which colours every tile icon.

The choices table SHALL show a **Color** column next to Icon. Each cell SHALL hold a colour swatch and a control that clears it. A cleared cell SHALL save no `color` for that option, and the option then follows the question colour. As with Icon and Group, the column SHALL be hidden under other styles without losing its values.

#### Scenario: Color field appears with the grid
- **WHEN** the creator switches a choice question's "Display as" to Icon grid
- **THEN** the Color field becomes visible

#### Scenario: Per-option colour saves
- **WHEN** the creator sets one row's colour and saves
- **THEN** that choice entry carries `color`, and rows left cleared carry none

### Requirement: Dashboard card statistics
Each survey card on `/editor/` SHALL show *completed* and *completion %* computed over the
survey's whole version family (the canonical survey plus its archived versions, never the draft
copy), from non-deleted sessions, with a session counted as completed when it answered a
question of its own version's last section — the same numbers the Responses overview reports
for the default "all versions" scope. The dashboard SHALL compute these numbers for all its
cards together, in a number of database queries that does not grow with the number of surveys
listed; it SHALL NOT compute per-session issue flags, which no card shows.

#### Scenario: Card numbers match the Responses overview
- **WHEN** a survey has sessions on its canonical version and on an archived version, some of
  them completed, one deleted, and a preview session on its draft copy
- **THEN** its dashboard card shows the same completed count and completion % as
  `SurveyAnalyticsService(survey).get_overview()`

#### Scenario: Survey with no sessions
- **WHEN** a survey on the dashboard has no sessions
- **THEN** its card shows 0 completed and 0%

#### Scenario: Query count does not grow with the survey list
- **WHEN** the dashboard is rendered for a workspace with 2 surveys and again for one with 8
  surveys of the same shape
- **THEN** both renders run the same number of database queries

### Requirement: Survey settings accessible from the editor sidebar
The system SHALL show a pinned "Survey settings" entry above the section list in the Build space sidebar, styled identically to the "Page settings" pinned entry in the Publish space (shared `.sidebar-pinned`/`.sidebar-pinned-item` classes). Clicking it SHALL swap the center panel to a settings form (general fields, default map position, collaborators, password/test access) via HTMX without a full page reload, and SHALL mark the pinned entry active while clearing any active section. The general-fields form SHALL autosave on field change. Loading `/editor/surveys/<uuid>/?panel=settings` SHALL render the settings panel as the initial center-panel content with the pinned entry pre-selected. The navbar ⚙ button SHALL be the primary entry point to this panel.

#### Scenario: Open settings from the sidebar
- **WHEN** the user clicks the pinned "Survey settings" entry in the Build sidebar
- **THEN** the center panel swaps to the settings form (no full page reload), the pinned entry gets the active style, and no section item is shown as active

#### Scenario: Open settings from the navbar gear
- **WHEN** the user clicks the ⚙ button in the navbar
- **THEN** the browser opens the Build space with the settings panel selected

#### Scenario: Deep link opens settings directly
- **WHEN** the user loads `/editor/surveys/<uuid>/?panel=settings`
- **THEN** the initial center-panel content is the settings form and the pinned entry renders with the active style server-side

### Requirement: Minimal survey creation
The Create New Survey page SHALL ask only for the survey name, the available
languages, and the map respondents will see — framed as "the map people will
see", not "your survey area".

The map block SHALL be WYSIWYG: the picker shows exactly the view respondents
open on, the map CENTRE is the survey's start position, and a fixed centre pin
marks it. The start position and zoom SHALL be kept in sync with the map centre
live (so a point is always set — the creator never has to click to drop a
marker), and framing the map via drag, place search, "My location", or creator
auto-geolocation SHALL update it. The base map SHALL be chosen through an on-map
dropdown control (a compact toggle, top-right, that opens a click-to-select menu
with icons — not a permanently-expanded radio list) that both switches the
preview and sets the survey's default base map; all base maps remain available
to respondents.

All other survey configuration (redirect URL, visibility, thanks page, cover
image, which base maps are enabled, and the respondent auto-center behavior)
SHALL NOT appear on the creation form; a newly created survey SHALL receive the
model defaults for those fields, and the page SHALL point the creator to the
Survey settings panel for them.

#### Scenario: Create with name only
- **WHEN** a creator submits the form with just a name (languages and map
  untouched)
- **THEN** the survey is created with default settings (private visibility,
  `#` redirect, all basemaps enabled, empty thanks/languages, auto-center off)
  and the creator lands in the Build space

#### Scenario: Create with languages chosen
- **WHEN** a creator picks one or more languages before submitting
- **THEN** the created survey stores exactly those `available_languages`

#### Scenario: The framed map centre becomes the start position
- **WHEN** a creator frames the map (drag / search / My location) so a place
  sits under the centre pin, then submits
- **THEN** the created survey stores the map centre and zoom as its start
  position — i.e. exactly the view respondents will open on

#### Scenario: Pick the base map from the on-map dropdown
- **WHEN** a creator opens the layers control on the map and selects Satellite
  (or Topo)
- **THEN** the picker preview switches to that provider and the created survey
  stores it as `default_basemap`, with all base maps still enabled; an unknown
  value is ignored

#### Scenario: Search the map for a place
- **WHEN** a creator types a place name into the map search and picks a result
- **THEN** the map recentres on that place and the start position is set to it
  (the platform-wide place search — see the `map-place-search` capability)

#### Scenario: Jump to my location
- **WHEN** a creator clicks the "My location" button and grants geolocation
- **THEN** the map recentres on the creator's current position and the start
  position is set to it; if permission is denied the coords line explains how
  to set the area another way

#### Scenario: Full settings remain editable after creation
- **WHEN** the creator opens the Survey settings panel of the new survey
- **THEN** all the fields absent from the creation form (including the
  auto-center-on-respondent toggle) are present and editable there

### Requirement: Standalone settings page remains reachable but is not linked
The standalone `/editor/surveys/<uuid>/settings/` URL and view SHALL continue to function (same template, same GET/POST behavior) for existing direct links and tests, but SHALL no longer be linked from the navbar or the dashboard cards — the ⚙ button and the in-Build panel are the entry points.

#### Scenario: Direct link to the old settings URL still works
- **WHEN** a user navigates directly to `/editor/surveys/<uuid>/settings/`
- **THEN** the standalone settings page renders as before

### Requirement: Lifecycle spaces navigation
The survey-management navbar SHALL present three spaces of equal rank — **Build** (survey construction), **Results** (responses & analysis), and **Publish** (public results page) — as the only tabs. The underlying routes and view names SHALL be unchanged (`editor_survey_detail`, `editor_survey_analytics`, `editor_survey_public_results`). `Share` and `Preview` SHALL be navbar action dropdowns rather than tabs, and survey settings SHALL be reachable via a ⚙ button that opens the in-Build settings panel; there SHALL be no standalone Settings tab.

#### Scenario: Three spaces shown
- **WHEN** an editor opens any survey-management page
- **THEN** the tab row shows exactly Build, Results, and Publish, with the current space marked active

#### Scenario: Share and Preview are actions
- **WHEN** the editor opens the `Share` dropdown
- **THEN** it offers to copy the survey link, show a QR code, open tracking links, and (when the results page is live) copy the results-page link
- **AND** the `Preview` dropdown offers the survey as a respondent and the results page

#### Scenario: Settings via gear
- **WHEN** the editor clicks the ⚙ button
- **THEN** the Build space opens with the survey-settings panel selected (equivalent to `?panel=settings`), and no Settings tab is present in the navbar

### Requirement: Unified publishing widget
The navbar SHALL provide a single publishing widget (the status chip) that, for owners, opens a dropdown grouping: Collection (survey status transitions), Discovery (public-gallery visibility), Results page (live state and link), and Version (version number and draft actions). The widget SHALL be presentation over existing fields (`status`, `visibility`, `PublicResultsPage.is_published`) and SHALL NOT introduce new lifecycle states. The widget SHALL appear consistently across the Build, Results, and Publish spaces.

#### Scenario: Widget groups the publish controls
- **WHEN** an owner opens the publishing widget on a published survey
- **THEN** it shows the collection status with transition actions, a gallery-visibility toggle, the results-page state with its `/r/<slug>/` link, and the version/draft section

#### Scenario: Gallery visibility toggle
- **WHEN** an owner toggles "Listed in public gallery" on
- **THEN** the survey `visibility` becomes `public`; toggling off sets it `private`; no other field changes

#### Scenario: Non-owner sees a static chip
- **WHEN** a non-owner opens a survey-management page
- **THEN** the status chip renders as a static badge without transition/visibility controls

### Requirement: Results space
The analytics surface SHALL be presented as the **Results** space (one of the three top-level spaces). Its existing split-pane Data workspace (where Table, Map, and Charts can be shown simultaneously in resizable panes) and the Performance report SHALL be preserved as internal sub-navigation of Results — they are NOT flattened into mutually-exclusive sidebar items, because that would remove the split-pane capability. Data download SHALL be available directly within the Results space. All analytics endpoints and behaviors SHALL be unchanged.

#### Scenario: Results is one space
- **WHEN** the editor opens the Results space
- **THEN** the navbar marks Results active and the split-pane Data workspace and Performance sub-views remain available

#### Scenario: Download from Results
- **WHEN** the editor is in the Results space
- **THEN** a "Download data" action is available without leaving the space

### Requirement: Editor layout adapts below 768px
On viewports narrower than 768px the survey editor SHALL NOT rely on the three-pane
side-by-side layout: exactly one pane is presented at a time (see
`editor-mobile-navigation`), the page SHALL have no horizontal overflow, and all
interactive controls SHALL meet a 44px minimum touch target. The desktop three-pane layout
SHALL remain unchanged at 768px and above.

#### Scenario: No horizontal overflow on mobile
- **WHEN** the editor is opened at 390px width with the mobile navigation flag enabled
- **THEN** the document's scroll width does not exceed the viewport width

#### Scenario: Read-only banner fits mobile
- **WHEN** a published (read-only) survey version is opened at 390px width
- **THEN** the read-only banner renders without overlapping its own text and its action button is fully visible

### Requirement: The survey nav's dropdowns work on every page that renders it
Any editor page that includes the survey nav tabs SHALL also load the script defining the nav's
dropdown handler. A page that renders the nav without it presents Share and Preview buttons that
throw `ReferenceError` and open nothing. This SHALL hold under both states of the
`MOBILE_EDITOR_NAV` kill switch, since its off state is the rollback path and is exactly the state
in which those dropdowns render on every tab.

#### Scenario: Share page dropdowns open
- **WHEN** the Share page is rendered with `MOBILE_EDITOR_NAV` off
- **THEN** the nav's dropdown handler is defined on the page, not only referenced

#### Scenario: Settings page dropdowns open
- **WHEN** the survey Settings page is rendered with `MOBILE_EDITOR_NAV` off
- **THEN** the nav's dropdown handler is defined on the page, not only referenced

### Requirement: Numbers emitted into JavaScript are locale-independent
Any number the editor interpolates into inline JavaScript, a `data-*` attribute read by script, or any other machine-parsed context SHALL be rendered without locale formatting. `USE_L10N` is on and every non-English language in `LANGUAGES` writes decimals with a comma, so an unguarded float turns `52.52` into `52,52` and makes the surrounding script fail to parse.

Numbers shown to a person as text SHALL remain localized.

#### Scenario: Map picker initialises under a comma-decimal UI
- **WHEN** the section map picker is rendered for a creator whose UI language writes decimals with a comma
- **THEN** the coordinates in its script are written with a decimal point and the script parses

#### Scenario: Survey settings map initialises under a comma-decimal UI
- **WHEN** the survey settings map block is rendered under such a locale
- **THEN** its coordinates are written with a decimal point

#### Scenario: Numeric question statistics parse under a comma-decimal UI
- **WHEN** the Responses page renders the histogram script for a numeric question under such a locale
- **THEN** the minimum and maximum are written with a decimal point

#### Scenario: Coordinate readouts stay localized for the reader
- **WHEN** the panel shows a coordinate as text for the creator to read
- **THEN** it is formatted for their locale

### Requirement: Question modal validation errors are shown in the modal

When a question create, edit or sub-question create POST fails validation (form errors or a Visibility-block error) and the modal is re-rendered, the response SHALL be swapped into the modal body (`#questionModalBody`) and not into the form's success target (the question list or a list item). The server SHALL express this with the HTMX `HX-Retarget`/`HX-Reswap` response headers so no client script is required.

#### Scenario: Conditional mode without answers on create

- **WHEN** a creator submits the New question form with "Shown conditionally" selected
  and no answer of the controlling question ticked
- **THEN** the modal re-renders in place with the error "Pick a controlling question and
  at least one of its answers.", the question list is unchanged, and no question is
  created

#### Scenario: Invalid edit form

- **WHEN** an edit POST (non-autosave) fails validation
- **THEN** the modal re-renders in place and the question's list item is not replaced
  by the modal markup

### Requirement: Visibility block works in the question modal while the section panel is open

The Visibility block SHALL bind its picker behaviour per rendered instance, so that the
question modal's block works regardless of whether the section panel (which renders its
own block) is open on the same page. The block SHALL NOT rely on a page-unique element id.

#### Scenario: Picker unfolds in the modal next to an open section panel

- **WHEN** the section panel is open and the creator opens a question modal and selects
  "Shown conditionally"
- **THEN** the "When the answer to" select and the answer checkboxes of the modal's block
  become visible

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

### Requirement: Editor panel autosave error reporting
The system SHALL autosave every editor panel that has no explicit Save button — Survey settings, the Thanks page and Public results — through one shared implementation, and SHALL distinguish a failure the creator can act on from one they can only retry.

When a save is refused with HTTP 400 carrying an `errors` object, the panel SHALL name the
first failing field by the label the creator sees and quote its message, SHALL mark that
field as invalid, and SHALL NOT offer a retry, because re-posting the same value cannot
succeed. When a save fails for any other reason — a network error, a 403, a 5xx — the panel
SHALL say the save did not reach the server and SHALL make its status indicator a retry
control. A subsequent successful save SHALL clear every message and field mark the panel set.

An autosaver SHALL claim only the forms it was written for: the question-form autosaver SHALL
skip a form that carries no `hx-post`, so an editor panel is never saved twice, never posted to
a null URL, and never has another module's failure written into its status indicator.

Controls that live inside an autosaving form but save through their own endpoint — the
reference-layer card, the survey's auto-center switch, the Public results slug — SHALL NOT
trigger that form's autosave.

#### Scenario: A rejected field is named
- **WHEN** a creator types a malformed address into "Redirect URL" in the Survey settings panel and the server answers 400 with `{"errors": {"redirect_url": ["Enter a valid URL."]}}`
- **THEN** the status reads "Not saved — Redirect URL: Enter a valid URL.", the redirect_url input is marked invalid, and the status offers no retry

#### Scenario: A transport failure offers a retry
- **WHEN** a save fails because the request never reaches the server
- **THEN** the status says the change was not saved and names a retry, and clicking the status re-sends the save

#### Scenario: Retrying an invalid value is not offered
- **WHEN** the status is showing a validation failure and the creator clicks it
- **THEN** no request is sent

#### Scenario: A later success clears the report
- **WHEN** a validation failure has named a field and the creator corrects it, and the next save succeeds
- **THEN** the status returns to the saved state and the field is no longer marked invalid

#### Scenario: One implementation, not three copies
- **WHEN** the Survey settings, Thanks page and Public results panels render
- **THEN** each loads the shared panel autosave module and none of them defines an autosave status handler of its own

#### Scenario: One autosaver per form
- **WHEN** the Survey settings panel renders and a creator changes any field
- **THEN** only the panel autosaver posts, to the form's own action — the question autosaver does not claim the form, posts nothing, and writes nothing into the map position indicator that shares the form

#### Scenario: No redirect is a valid choice
- **WHEN** a creator clears "Redirect URL" in the Survey settings panel and the panel autosaves
- **THEN** the save succeeds and the survey stores the "#" sentinel that means "no redirect", rather than the panel refusing every later save with "This field is required"

#### Scenario: The auto-center switch does not fire the settings autosave
- **WHEN** a creator toggles "Auto-center on respondent's location" in the Survey settings panel
- **THEN** the map position endpoint receives the change and the settings form posts nothing, so a settings validation error cannot appear under the switch

### Requirement: Every disabled edit control on a live survey opens the new-version sheet
On a published or closed survey, clicking any disabled structural-edit control (New Question in the section panel or sidebar, Add sub-question, Paste question, question rows, section fields) SHALL open the "This survey is live and collecting responses" sheet offering "Open a new version" — regardless of which wrapper element receives the click.

#### Scenario: New Question in the section panel
- **WHEN** the creator clicks the disabled New Question button below the question list of a published survey
- **THEN** the live-survey sheet opens with "Open a new version"

### Requirement: Map position autosave survives its panel being replaced

A pending save SHALL be cancelled when its picker's container is removed, so nothing
fires against a detached DOM. If a save is nevertheless attempted and the fields it needs
cannot be read, it SHALL be abandoned rather than sent with a substituted value: posting a
default for a control the creator never touched would persist a choice they did not make.
Neither path SHALL raise.

The pickers save after a debounce pause, and the editor's settings panel is an HTMX
fragment that can be swapped away before that pause elapses; when it is, the elements the
pending save reads are gone.

#### Scenario: The panel is swapped away mid-pause

- **WHEN** a creator moves the map and navigates to another editor page before the debounce elapses
- **THEN** the pending save is cancelled, no request is sent, and no exception is raised

#### Scenario: A save whose fields have gone is abandoned, not guessed

- **WHEN** a save runs while the control backing one of its fields is absent from the DOM
- **THEN** no request is sent, and no value is written for that field

#### Scenario: A settled move still saves

- **WHEN** a creator moves the map and leaves the panel open past the debounce
- **THEN** the position is saved and the indicator reports success, unchanged from the current behaviour

#### Scenario: Teardown and guard are independently verified

- **WHEN** the teardown hook is absent but the fields are unreadable
- **THEN** the save is still abandoned without raising, so a missed teardown degrades to a skipped save rather than an exception

### Requirement: Settings panel saves the language picker
The Survey settings panel autosave SHALL save `available_languages` whenever the creator adds or
removes a language in the language picker, with no other gesture. Typing in the picker's search box
SHALL NOT trigger a save. Opening the panel SHALL NOT trigger a save.

#### Scenario: A language added in the panel survives a reload
- **WHEN** the owner of an English survey picks "Spanish" in the settings panel's language picker and reopens the panel
- **THEN** SurveyHeader.available_languages is `["en", "es"]` and the picker shows both languages

#### Scenario: Filtering then picking saves the picked language
- **WHEN** the owner types "spa" in the picker's search box and clicks "Spanish"
- **THEN** the last settings POST carries `available_languages` containing `"es"`, and no POST is sent by the search box itself

#### Scenario: A removed language is saved
- **WHEN** the owner removes a language tag in the picker
- **THEN** SurveyHeader.available_languages no longer contains that language

### Requirement: Creators duplicate a whole survey
The dashboard's ⋯ menu SHALL offer "Duplicate" on every survey to workspace members who may create
surveys. It SHALL create the copy described for `POST /surveys/{uuid}/duplicate` through the same
service and open the copy's Build page. The source survey SHALL be unchanged whatever its status.

#### Scenario: Duplicate from the dashboard
- **WHEN** a workspace editor chooses Duplicate on a closed survey named "Benches 2026"
- **THEN** the editor opens a new draft survey "Benches 2026 (copy)" with the same sections, questions and layers and no responses

#### Scenario: Viewer sees no Duplicate
- **WHEN** a workspace viewer opens the ⋯ menu
- **THEN** there is no Duplicate item

### Requirement: Creators move a question to another section
Each top-level question row SHALL offer "Move to section…", listing the survey's other sections.
Choosing one SHALL move the question to the end of that section, with its sub-questions and answers,
through the move service. The question SHALL leave its group. A toast SHALL name every visibility
rule the move cleared. On a live survey the control SHALL open the structure gate instead.

#### Scenario: Move a question to the next section
- **WHEN** a creator chooses "Move to section… → Section 2" on a question of Section 1 in a draft survey
- **THEN** the question is the last question of Section 2 and no longer listed under Section 1

#### Scenario: Live survey
- **WHEN** the survey is published and has no unpublished changes
- **THEN** the control opens the "Change the structure of a live survey" gate

### Requirement: Copies into another survey own their files
Pasting a question or section into another survey, and duplicating a survey, SHALL store a new copy
of every cover image, question image and layer attachment under a new key. Purging either survey
from the trash SHALL never delete a file the other uses. Copies within one survey and its versions
MAY share files, because they are purged together.

#### Scenario: Purge the source after a paste
- **WHEN** a question with an image is pasted from survey A into survey B and A is purged from the trash
- **THEN** B's question image still loads

