## REMOVED Requirements

### Requirement: A creator can choose how a range question is displayed

Removed. Production usage (122 of 124 range questions on the default slider; the only two
exceptions are one creator imitating the `rating` type) showed the control blurred the range /
rating distinction instead of serving a range need. A labelled discrete scale is the `rating`
type's job, and the question type picker now routes creators there.

## ADDED Requirements

### Requirement: A range question always renders as the slider

A `range` question SHALL render as the slider for respondents and in editor previews, regardless
of any `display_style` value stored on the question. Stored values SHALL be ignored without
error and without being rewritten.

#### Scenario: Stored choice-based style is ignored

- **WHEN** a range question whose stored `display_style` is `list_pips` or `scale_strip` is
  rendered to a respondent
- **THEN** it renders as the slider
- **AND** the stored value is unchanged in the database

#### Scenario: The editor does not offer styles for range

- **WHEN** a creator selects the range type in the question dialog
- **THEN** the "Display as" control is not offered

#### Scenario: The live preview cannot render the removed combination

- **WHEN** the question dialog's live preview is requested with `input_type=range` and a
  choice-based `display_style`
- **THEN** the preview renders the slider

### Requirement: Storage and collected answers are unaffected

Range answers SHALL continue to be stored in `Answer.numeric`; answers collected while a
choice-based style was in effect SHALL remain valid, exportable, and prepopulated when the
respondent navigates back.

#### Scenario: Answers collected under a removed style survive

- **WHEN** a range question that once rendered as a labelled list has stored answers and now
  renders as the slider
- **THEN** the stored numeric answers are unchanged and the slider prepopulates from them
