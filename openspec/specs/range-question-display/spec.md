# range-question-display Specification

## Purpose

How a `range` question is presented to the respondent: the slider's geometry and labelling, and
what happens to questions carrying display-style values from the period when styles were briefly
offered for range.

## Requirements
### Requirement: A range question always renders as the slider

A `range` question SHALL render as the slider for respondents and in editor previews, regardless
of any `display_style` value stored on the question, and regardless of the survey-wide rating
display style. Stored values SHALL be ignored without error and without being rewritten.

#### Scenario: Stored choice-based style is ignored

- **WHEN** a range question whose stored `display_style` is `list_pips` or `scale_strip` is
  rendered to a respondent
- **THEN** it renders as the slider
- **AND** the stored value is unchanged in the database

#### Scenario: The survey-wide rating style is not inherited

- **WHEN** a range question has `display_style = 'default'`
- **THEN** it renders as a slider, whatever the survey's `rating_display_style` is set to

#### Scenario: The editor does not offer styles for range

- **WHEN** a creator selects the range type in the question dialog
- **THEN** the "Display as" control is not offered

#### Scenario: The live preview cannot render the removed combination

- **WHEN** the question dialog's live preview is requested with `input_type=range` and a
  choice-based `display_style`
- **THEN** the preview renders the slider

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

### Requirement: A range question without choices remains usable

If a `range` question has no choices defined, it SHALL still render as a usable slider. This is a
live path, not a defensive one: a substantial share of production range questions have no choices.

#### Scenario: No choices defined

- **WHEN** a range question with no choices is rendered
- **THEN** it renders as a slider
- **AND** the page renders without error

### Requirement: Storage and collected answers are unaffected

Range answers SHALL be stored in `Answer.numeric`. Answers collected while a choice-based style
was in effect SHALL remain valid, exportable, and prepopulated when the respondent navigates back.

#### Scenario: Answers collected under a removed style survive

- **WHEN** a range question that once rendered as a labelled list has stored answers and now
  renders as the slider
- **THEN** the stored numeric answers are unchanged and the slider prepopulates from them

#### Scenario: Answers stay in their export column

- **WHEN** a range question's stored display style changes or is ignored
- **THEN** existing answers are unchanged and continue to appear in the export under the same
  column

### Requirement: An unanswered range question produces no answer row

A `range` question left unanswered SHALL produce no answer row and SHALL NOT error.

Note: this deliberately does **not** say the submission is rejected. Answers are not validated
server-side at all — the POST handler builds the form with `initial=request.POST`, so it is never
bound and `required` is never enforced, for any question type. That is a pre-existing
platform-wide gap, recorded separately.

#### Scenario: Nothing selected

- **WHEN** a range question is submitted with its field absent
- **THEN** no answer row is created
- **AND** the request completes without error
