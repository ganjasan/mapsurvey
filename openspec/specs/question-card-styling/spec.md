## ADDED Requirements

### Requirement: Question card wrapping
Questions with input types `text`, `text_line`, `number`, `choice`, `multichoice`, and `range` SHALL be rendered inside a card wrapper element with class `question-card`.

#### Scenario: Text question renders in card
- **WHEN** a survey section contains a question with input_type `text`
- **THEN** the question's label and input SHALL be wrapped in a `div.question-card` element

#### Scenario: Choice question renders in card
- **WHEN** a survey section contains a question with input_type `choice`
- **THEN** the question's label and radio inputs SHALL be wrapped in a `div.question-card` element

#### Scenario: Geo question does not render in card
- **WHEN** a survey section contains a question with input_type `point`, `line`, or `polygon`
- **THEN** the question SHALL render without a `div.question-card` wrapper

#### Scenario: HTML question does not render in card
- **WHEN** a survey section contains a question with input_type `html`
- **THEN** the question SHALL render without a `div.question-card` wrapper

#### Scenario: Image question does not render in card
- **WHEN** a survey section contains a question with input_type `image`
- **THEN** the question SHALL render without a `div.question-card` wrapper

#### Scenario: Rating question does not render in card
- **WHEN** a survey section contains a question with input_type `rating`
- **THEN** the question SHALL render without a `div.question-card` wrapper

### Requirement: Card visual styling
Each `.question-card` element SHALL have white background, padding, border-radius, and a light border for visual separation.

#### Scenario: Card appearance
- **WHEN** a question-card is rendered
- **THEN** it SHALL have white background (`#ffffff`), `12px` padding, `8px` border-radius, and `1px solid #e0e0e0` border

#### Scenario: Card spacing
- **WHEN** multiple questions are rendered in sequence
- **THEN** each `.question-card` SHALL have `12px` bottom margin

### Requirement: Custom template iteration replaces form.as_p
The `survey_section.html` template SHALL iterate form fields individually instead of using `{{ form.as_p }}`.

#### Scenario: Field-by-field rendering
- **WHEN** a survey section is rendered
- **THEN** the template SHALL iterate over `form` fields, rendering each field's label, errors, and widget individually

#### Scenario: Hidden fields rendered separately
- **WHEN** the form contains hidden fields
- **THEN** hidden fields SHALL be rendered outside the card iteration loop

### Requirement: Widget exposes input_type
Each widget instance in `SurveySectionAnswerForm` SHALL have an `input_type` attribute set to the question's `input_type` value.

#### Scenario: Widget input_type attribute
- **WHEN** a form field is created for a question with input_type `choice`
- **THEN** the field's widget SHALL have `widget.input_type == "choice"`

### Requirement: Custom radio button styling
Radio buttons (used by `choice` and `rating` input types) SHALL be styled with CSS-only custom appearance replacing the native browser radio input.

#### Scenario: Radio visual appearance
- **WHEN** a radio button is rendered
- **THEN** the native input SHALL be visually hidden and replaced by a styled circular indicator via CSS pseudo-elements

#### Scenario: Radio checked state
- **WHEN** a radio option is selected
- **THEN** the circular indicator SHALL show a filled inner circle with a transition animation

#### Scenario: Radio touch target
- **WHEN** a radio option label is rendered
- **THEN** the label SHALL have a minimum height of `44px` for WCAG-compliant touch targets

### Requirement: Custom checkbox styling
Checkboxes (used by `multichoice` input type) SHALL be styled with CSS-only custom appearance replacing the native browser checkbox.

#### Scenario: Checkbox visual appearance
- **WHEN** a checkbox is rendered
- **THEN** the native input SHALL be visually hidden and replaced by a styled square indicator via CSS pseudo-elements

#### Scenario: Checkbox checked state
- **WHEN** a checkbox option is selected
- **THEN** the square indicator SHALL show a checkmark with a transition animation

#### Scenario: Checkbox touch target
- **WHEN** a checkbox option label is rendered
- **THEN** the label SHALL have a minimum height of `44px` for WCAG-compliant touch targets

### Requirement: Geo button visual consistency
The `.drawbutton` element SHALL have border-radius and spacing consistent with question cards.

#### Scenario: Geo button border-radius
- **WHEN** a geo question draw button is rendered
- **THEN** it SHALL have `8px` border-radius matching question cards

#### Scenario: Geo button spacing
- **WHEN** a geo question draw button is rendered
- **THEN** it SHALL have `12px` bottom margin matching question card spacing
