## MODIFIED Requirements

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
