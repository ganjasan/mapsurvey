# question-subtext Specification

## Purpose

Where a question's subtext reaches the respondent, per input type — including the two types that
deliberately do not show their name.
## Requirements
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

### Requirement: A rich-text hint renders once, inside its styled wrapper
Wherever a question's subtext or an image block's caption is shown to a respondent or in the editor's preview, the creator's rich text SHALL be placed inside a block-level wrapper, so that the browser keeps it inside the styled hint element. The hint SHALL appear exactly once and SHALL keep the hint style (smaller and muted relative to the question title).

#### Scenario: Geo question with a rich-text hint
- **WHEN** a respondent opens a section with a line question whose subtext is `<p>Subtest</p>`
- **THEN** the draw button shows "Subtest" once, in the muted subtitle style below the title

#### Scenario: Card question with a rich-text hint
- **WHEN** a respondent opens a section with a choice, text or rating question whose subtext is
  rich text
- **THEN** the hint renders inside the `question-card__subtext` element in the muted style

#### Scenario: Image block with a rich-text caption
- **WHEN** an image block has a rich-text caption
- **THEN** the caption renders inside the `image-block__caption` element

### Requirement: Sub-questions in a map popup render like section questions
The popup that opens on a placed feature and the object popup of an "Objects on the map" question SHALL render their sub-questions through the same per-question markup as the section form, so each sub-question shows its hint between its text and its input and keeps its display style.

#### Scenario: Hint in a feature popup
- **WHEN** a respondent places a point whose question has a sub-question with a hint
- **THEN** the popup shows the hint under the sub-question's text, in the hint style

#### Scenario: Rating style in a popup
- **WHEN** a rating sub-question uses the stars, labeled list or compact scale style
- **THEN** the popup renders that style, not bare radio buttons

#### Scenario: Answers survive the popup
- **WHEN** a respondent answers sub-questions, closes the popup and opens it again
- **THEN** the answers are restored and are saved with the feature on submit

