## ADDED Requirements

### Requirement: Subtext is shown wherever a question collects an answer

A question's subtext SHALL be shown to the respondent for every input type that collects an
answer — `text`, `text_line`, `number`, `choice`, `multichoice`, `range`, `rating`, `datetime` —
positioned between the question text and the input, and SHALL appear in the editor's preview of
that question.

#### Scenario: Subtext under an ordinary question

- **WHEN** a text question with subtext is rendered to a respondent
- **THEN** the subtext appears after the question text and before the input

#### Scenario: Subtext under a scale question

- **WHEN** a rating question with subtext renders in any display style
- **THEN** the subtext appears after the question text and before the scale

#### Scenario: The editor preview agrees with the survey

- **WHEN** the question dialog previews a draft carrying subtext
- **THEN** the preview shows it

### Requirement: Geo questions and Formatted Text keep their existing subtext placement

`point`, `line` and `polygon` SHALL keep showing subtext inside the draw button, and `html` SHALL
keep rendering its subtext as the block's content.

#### Scenario: Geo subtext is unchanged

- **WHEN** a geo question with subtext renders
- **THEN** the subtext appears within the draw button, as before

### Requirement: An image block can be captioned

An `image` block SHALL render its subtext as a caption with the picture.

#### Scenario: Captioned image

- **WHEN** an image block with subtext renders
- **THEN** the subtext appears with the picture

### Requirement: The Name is not shown to respondents for image and Formatted Text blocks

For `image` and `html`, `Question.name` SHALL NOT be rendered to the respondent. For these two
types the name identifies the block in the editor, and published surveys use internal labels
there.

#### Scenario: Internal block names stay internal

- **WHEN** an image block named `image_1` and a Formatted Text block named `html_block_1` render
- **THEN** neither name appears on the respondent's page
