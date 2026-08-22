# rating-display-style Specification

## Purpose
How rating questions render for respondents: two visual styles (compact numeric scale strip and labeled list with intensity pips), a survey-wide default in `SurveyHeader.style_settings`, and per-question overrides via `Question.display_style`.

## Requirements
### Requirement: Display style field
The `Question` model SHALL have a `display_style` field with exactly three allowed values — `default`, `scale_strip`, `list_pips` — defaulting to `default`. The `SurveyHeader` model SHALL have a `style_settings` JSON field whose `rating_display_style` key defines the survey-wide default visual style (`scale_strip` when unset or invalid). A question with `display_style = "default"` SHALL render with the survey-wide default; an explicit per-question value SHALL win over the survey default. The fields SHALL only affect the rendering of questions with input_type `rating`; for all other input types they SHALL be ignored.

#### Scenario: Existing questions get the default
- **WHEN** the migration adding `display_style` is applied to a database with existing rating questions
- **THEN** every existing question has `display_style = "default"` and renders as a scale strip (the built-in survey default)

#### Scenario: Survey default applies to inheriting questions
- **WHEN** a survey has `style_settings.rating_display_style = "list_pips"` and a rating question has `display_style = "default"`
- **THEN** the question renders as a labeled list

#### Scenario: Per-question override wins over survey default
- **WHEN** a survey has `style_settings.rating_display_style = "list_pips"` and a rating question has `display_style = "scale_strip"`
- **THEN** that question renders as a scale strip

#### Scenario: Questions in one section render independently
- **WHEN** one section contains two rating questions, one resolved to `scale_strip` and one to `list_pips`
- **THEN** each question renders in its own style on the same page

#### Scenario: Editing one question's style does not affect siblings
- **WHEN** the editor saves a new `display_style` for one rating question
- **THEN** the `display_style` of every other question in the survey is unchanged

#### Scenario: Non-rating question ignores the field
- **WHEN** a question with input_type `choice` has `display_style = "list_pips"`
- **THEN** the question renders exactly as choice questions rendered before this change

### Requirement: Scale strip rendering
A rating question whose resolved style is `scale_strip` SHALL render as a single row of equal-width numbered cells (1..N, one per choice, in choice order), with the translated names of the first and last choices as anchor labels below the row, and a label chip area below the anchors. Selecting a cell SHALL highlight it with the accent color and show the selected choice's translated name in the label chip. The row SHALL keep one line for any number of choices (including 7+).

#### Scenario: Five-point worded scale renders as strip
- **WHEN** a rating question has 5 choices "very unsure" … "very confident" and `display_style = "scale_strip"`
- **THEN** the survey section shows one row of 5 numbered cells with "very unsure" and "very confident" as anchors below, and no full-width wrapping pill buttons

#### Scenario: Selection shows the label chip
- **WHEN** the respondent clicks cell 4 of the strip
- **THEN** cell 4 is highlighted with the accent color and the chip below shows the translated name of choice 4

#### Scenario: Anchors and chip use the survey language
- **WHEN** the respondent has selected language "de" and the choices have German translations
- **THEN** the anchors and the selected-label chip show the German choice names

#### Scenario: Prepopulated answer restores strip state
- **WHEN** the respondent navigates back to a section where they previously answered a scale-strip rating question
- **THEN** the previously chosen cell renders highlighted and the chip shows its label without further interaction

#### Scenario: Seven-point scale stays on one row
- **WHEN** a rating question has 7 choices and `display_style = "scale_strip"`
- **THEN** all 7 cells render in a single row of equal-width cells

### Requirement: List pips rendering
A rating question whose resolved style is `list_pips` SHALL render as a vertical list of full-width option rows in choice order, each row showing the translated choice name and a right-aligned pip indicator with N dots of which the first n are filled (n = 1-based position of the option, N = total choices). Selecting a row SHALL highlight it with the accent color.

#### Scenario: Five-point worded scale renders as list
- **WHEN** a rating question has 5 choices and `display_style = "list_pips"`
- **THEN** the survey section shows 5 stacked full-width rows, each with its choice name and a 5-dot pip indicator (row k has k filled dots)

#### Scenario: Long labels do not break layout
- **WHEN** a choice name is long (e.g. "sehr zuversichtlich") in a 420px panel
- **THEN** the row wraps its text without horizontal overflow and rows keep equal width

#### Scenario: Selecting a row highlights it
- **WHEN** the respondent clicks the row "rather confident"
- **THEN** that row (and only that row) renders in the selected accent state

### Requirement: Radio semantics preserved
Both display styles SHALL be backed by the same radio-group form field as before: one selectable value per question, submitted under the same field name with the choice code as the value, stored in `Answer` unchanged.

#### Scenario: Submission stores the choice code
- **WHEN** the respondent selects option with code 4 in either display style and submits the section
- **THEN** the stored Answer for that question records choice code 4, identical to submissions made before this change

### Requirement: Cloning preserves display style
All question-cloning paths (versioning draft clone, editor duplicate, copy/paste) SHALL copy `display_style` to the new question.

#### Scenario: Draft clone keeps the style
- **WHEN** a published survey containing a rating question with `display_style = "list_pips"` is cloned for a draft
- **THEN** the cloned question has `display_style = "list_pips"`

