## MODIFIED Requirements

### Requirement: Input types are presented in groups with icon, hint and example

The question editor SHALL present input types as a grouped picker — real questions, map questions,
files, and display blocks that collect nothing — where each type carries an icon, its display label
and a one-line hint of what the respondent does. Hovering a type SHALL show a canned example of
that type as a respondent would see it. The Files group SHALL appear only while
`FILE_UPLOAD_QUESTIONS` is enabled. The *Questions* group SHALL include `thumbs` ("Thumbs
up / down", `fa-thumbs-up`). The *Map questions* group SHALL include `layer_objects`
("Objects on the map", `fa-map-marked-alt`), which SHALL follow the same section-layout rule
as the geo types and SHALL be offered only when the survey has at least one reference layer
and the reference-layers kill switch is on.

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

#### Scenario: Objects on the map sits with the map questions

- **WHEN** a creator opens the picker on a map-layout section of a survey with a reference layer
- **THEN** `layer_objects` appears in the Map questions group after the geo types with the label "Objects on the map"

#### Scenario: Objects on the map hidden without a layer

- **WHEN** the survey has no reference layers, or the section layout is `form`
- **THEN** the picker does not offer `layer_objects`

#### Scenario: Thumbs is an ordinary question

- **WHEN** a creator opens the picker
- **THEN** `thumbs` appears in the Questions group with a thumbs-up icon and is offered for sub-questions too
