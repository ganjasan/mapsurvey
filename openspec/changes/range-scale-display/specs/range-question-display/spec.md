## ADDED Requirements

### Requirement: A range question is stored identically whatever its display style

The display style SHALL affect presentation only. A `range` answer SHALL be stored in
`Answer.numeric` regardless of which style rendered the question, and changing the style SHALL NOT
alter, invalidate, or split answers already collected.

#### Scenario: The same answer stored through each style

- **WHEN** a respondent selects the value `5` on a range question rendered as a slider, and another
  respondent selects `5` on the same question rendered as `scale_strip`
- **THEN** both answers are stored with `numeric = 5`

#### Scenario: Style changed after responses exist

- **WHEN** a creator changes a range question's display style and the survey already holds answers
- **THEN** the existing answers are unchanged
- **AND** they continue to appear in the export under the same column

### Requirement: Slider labels mark positions the respondent can reach

When a range question renders as a slider, the endpoint labels and the tick marks SHALL be
positioned against the range the slider's thumb can actually occupy, and SHALL agree with each
other.

#### Scenario: Endpoint labels align with the extreme thumb positions

- **WHEN** a range question renders as a slider
- **THEN** the first and last labels are positioned at the extreme positions the thumb can occupy,
  not at the outer edges of the slider element

#### Scenario: Ticks and labels share one alignment

- **WHEN** a range question renders as a slider
- **THEN** the tick row and the label row use the same horizontal inset

### Requirement: A creator can choose how a range question is displayed

A `range` question SHALL offer the same display styles as a `rating` question: the slider, a compact
scale strip, and a labelled list. The choice SHALL be made per question in the question editor.

#### Scenario: Display style control is offered for range questions

- **WHEN** a creator opens the question editor for a `range` question
- **THEN** the "Display as" control is shown, offering the slider, the scale strip and the labelled
  list

#### Scenario: Labelled list shows every choice's name

- **WHEN** a range question with nine named choices renders as `list_pips`
- **THEN** all nine names are present in the rendered output

#### Scenario: Scale strip shows the endpoint names as anchors

- **WHEN** a range question renders as `scale_strip`
- **THEN** one cell is rendered per choice
- **AND** the first and last choice names are shown as anchors beneath the strip

### Requirement: An unset display style renders a range question as a slider

For a `range` question, the `default` display style SHALL resolve to the slider. It SHALL NOT
inherit the survey-wide rating display style.

#### Scenario: Existing question keeps rendering as a slider

- **WHEN** a range question has `display_style = 'default'`
- **THEN** it renders as a slider, whatever the survey's `rating_display_style` is set to

### Requirement: A range question without choices remains usable

If a `range` question has no choices defined, it SHALL render as a slider regardless of the selected
display style, because the choice-based styles have nothing to lay out.

#### Scenario: Choice-based style falls back when there are no choices

- **WHEN** a range question with no choices has `display_style = 'scale_strip'`
- **THEN** it renders as a slider
- **AND** the page renders without error

### Requirement: An unanswered range question behaves the same in every style

A `range` question left unanswered SHALL produce no answer row and SHALL NOT error, identically in
every display style.

Note: this deliberately does **not** say the submission is rejected. Answers are not validated
server-side at all — the POST handler builds the form with `initial=request.POST`, so it is never
bound and `required` is never enforced, for any question type. That is a pre-existing platform-wide
gap, recorded separately; this requirement pins only that the display style does not change the
behaviour.

#### Scenario: Nothing selected in each style

- **WHEN** a range question is submitted with its field absent, rendered as a slider, as
  `scale_strip`, and as `list_pips` in turn
- **THEN** no answer row is created in any of the three
- **AND** the request completes without error
