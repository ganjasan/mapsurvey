# question-type-picker Specification

## Purpose

How the question editor presents the set of input types to a creator: grouping, naming,
iconography, per-type hints and examples, which settings fields are offered for which type, and
the live respondent-side preview of the question being configured.
## Requirements
### Requirement: Input types are presented in groups with icon, hint and example

The question editor SHALL present input types as a grouped picker — real questions, map questions,
files, and display blocks that collect nothing — where each type carries an icon, its display label
and a one-line hint of what the respondent does. Hovering a type SHALL show a canned example of
that type as a respondent would see it. The Files group SHALL appear only while
`FILE_UPLOAD_QUESTIONS` is enabled.

#### Scenario: Display blocks are visibly not questions

- **WHEN** a creator opens the type picker
- **THEN** `image` and `html` appear in a group labelled as display blocks that collect nothing,
  separated from answerable questions

#### Scenario: The html type reads "Formatted Text"

- **WHEN** the picker lists the `html` type
- **THEN** its label is "Formatted Text" with a paragraph icon
- **AND** the value submitted and stored remains `html`

#### Scenario: Sub-question restrictions are respected

- **WHEN** the dialog edits a sub-question
- **THEN** the picker offers exactly the types the form field's choices allow

#### Scenario: Files are their own group, distinct from the image display block

- **WHEN** a creator opens the type picker with file uploads enabled
- **THEN** `photo`, `audio` and `document` appear in a Files group of answerable questions
- **AND** the `image` display block stays in the display-blocks group, so "show a picture" and
  "collect a picture" cannot be confused

#### Scenario: Kill switch hides the group

- **WHEN** `FILE_UPLOAD_QUESTIONS` is off
- **THEN** the picker shows no Files group

### Requirement: Picker metadata cannot drift from the model

Every entry of `INPUT_TYPE_CHOICES` SHALL have picker metadata (group, icon, hint) and vice versa.

#### Scenario: A new model type without metadata fails tests

- **WHEN** a type is added to `INPUT_TYPE_CHOICES` without picker metadata
- **THEN** the parity test fails

### Requirement: The dialog previews the question as configured, before saving

The question dialog SHALL show a respondent-side preview of the question being configured — built
by the same server-side form machinery that renders the survey — reflecting the current unsaved
values of type, question text, choices, display style, colour and icon, for both new and existing
questions.

#### Scenario: Preview of an unsaved new question

- **WHEN** a creator picks `rating`, types a question text and defines choices `1=worst`, `5=best`
- **THEN** the preview pane shows that text over the rating scale built from those choices,
  without the question having been saved

#### Scenario: Preview updates on edit

- **WHEN** the creator changes the display style or a choice label
- **THEN** the pane re-renders to match without pressing Apply or Save

#### Scenario: Malformed choices do not break the preview

- **WHEN** the pane requests a render while `choices_json` is invalid
- **THEN** the endpoint renders the type's no-choices fallback rather than erroring

#### Scenario: Preview never persists anything

- **WHEN** the live preview endpoint is called for a new question
- **THEN** no `Question` row is created

### Requirement: Only fields the selected type consumes are offered

The dialog SHALL show Color and Icon class only for geo types (`point`, `line`, `polygon`), the
Image upload only for the `image` type, and SHALL NOT offer Required on display blocks. Hiding a
field SHALL NOT clear its stored value on save.

#### Scenario: Text question shows no dead controls

- **WHEN** the selected type is `text`
- **THEN** Color, Icon class and Image are not visible

#### Scenario: Hidden values survive a save

- **WHEN** a question with a stored colour is edited as a non-geo type and saved
- **THEN** the stored colour is unchanged

