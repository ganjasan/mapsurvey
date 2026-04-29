## ADDED Requirements

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

## MODIFIED Requirements

### Requirement: Question CRUD
The system SHALL allow creating, editing, deleting, and duplicating questions within a section via the WYSIWYG editor. Duplicating a question SHALL produce a clone immediately after the source (sibling-insert) with a freshly generated `code`, a `name` ending with ` (copy)`, and all other fields preserved including `validation_settings` and `image` path reference. The form SHALL include fields for name, subtext, input_type, required, color, icon_class, and image. Creating a question SHALL assign it the next order_number in the section.

(All existing scenarios for create / edit / delete preserved from the canonical spec; this requirement adds the duplicate action.)

#### Scenario: Duplicate a text question
- **WHEN** the user clicks Duplicate on a text question with `name="Feedback"` at `order_number=1`
- **THEN** a new Question is created with a fresh `code`, `name="Feedback (copy)"`, `order_number=2`; pre-existing siblings shift down.

### Requirement: Section CRUD
The system SHALL allow creating, editing, deleting, and duplicating sections within a survey. Duplicating a section SHALL produce a clone immediately after the source in the linked list (3-node splice), with a unique deduplicated `name`, a `title` ending with ` (copy)`, all questions and translations cloned, and `is_head=False`. Creating a section SHALL append it to the end of the linked list. Deleting a section SHALL re-link its neighbors. Editing SHALL support title, subheading, and code fields.

(All existing scenarios preserved; this requirement adds the duplicate action.)

#### Scenario: Duplicate a section
- **WHEN** the user clicks Duplicate on section B in linked list [A, B, C]
- **THEN** the linked list becomes [A, B, B', C] where B' has all of B's questions cloned with fresh codes and `B'.title = B.title + " (copy)"`.
