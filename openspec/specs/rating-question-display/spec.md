# rating-question-display Specification

## Purpose

How a `rating` question is presented to the respondent: the display styles available, how one is
chosen per question and survey-wide, what each style renders, and what stays true of the answer
regardless of style.

Consolidated from the former `rating-display-style` capability when the star style was added —
that spec pinned "exactly three allowed values", which stopped being true.

## Requirements
### Requirement: Display style field and resolution

The `Question` model SHALL have a `display_style` field allowing `default`, `scale_strip`,
`list_pips` and `stars`, defaulting to `default`. `SurveyHeader.style_settings.rating_display_style`
SHALL define the survey-wide default (`scale_strip` when unset or invalid). A question set to
`default` SHALL render with the survey-wide default; an explicit per-question value SHALL win.
The fields SHALL affect `rating` questions only and SHALL be ignored for every other input type.

#### Scenario: Survey default applies to inheriting questions

- **WHEN** a survey has `style_settings.rating_display_style = "list_pips"` and a rating question
  has `display_style = "default"`
- **THEN** the question renders as a labelled list

#### Scenario: Per-question override wins over survey default

- **WHEN** a survey defaults to `list_pips` and a rating question is set to `scale_strip`
- **THEN** that question renders as a scale strip

#### Scenario: Questions in one section render independently

- **WHEN** one section contains two rating questions resolving to different styles
- **THEN** each renders in its own style on the same page

#### Scenario: Non-rating question ignores the field

- **WHEN** a question with input type `choice` has `display_style = "list_pips"`
- **THEN** it renders exactly as choice questions render without the field

### Requirement: Scale strip rendering

A rating question resolved to `scale_strip` SHALL render as one row of equal-width numbered cells
(1..N, one per choice, in choice order), with the translated names of the first and last choices
as anchors below the row and a label chip below the anchors. Selecting a cell SHALL highlight it
and show that choice's translated name in the chip. The row SHALL stay on one line for any number
of choices.

#### Scenario: Five-point worded scale renders as a strip

- **WHEN** a rating question has five choices and resolves to `scale_strip`
- **THEN** one row of five numbered cells renders, anchored by the first and last choice names

#### Scenario: Selection shows the label chip

- **WHEN** the respondent selects cell 4
- **THEN** cell 4 is highlighted and the chip shows the translated name of choice 4

#### Scenario: Anchors and chip use the survey language

- **WHEN** the respondent has selected a language for which the choices have translations
- **THEN** the anchors and the chip show the translated names

#### Scenario: Prepopulated answer restores the strip state

- **WHEN** the respondent returns to a section they already answered
- **THEN** the previously chosen cell renders selected, with its label, without interaction

### Requirement: List pips rendering

A rating question resolved to `list_pips` SHALL render as a vertical list of full-width rows in
choice order, each showing the translated choice name and a right-aligned pip indicator of N dots
of which the first n are filled (n = the row's 1-based position). Selecting a row SHALL highlight
it.

#### Scenario: Five-point scale renders as a list

- **WHEN** a rating question has five choices and resolves to `list_pips`
- **THEN** five stacked full-width rows render, row k carrying k filled pips

#### Scenario: Long labels do not break the layout

- **WHEN** a choice name is long in a narrow panel
- **THEN** the row wraps its text without horizontal overflow and rows keep equal width

### Requirement: Star rendering

A rating question resolved to `stars` SHALL render one icon per choice, filled from the first icon
up to and including the respondent's selection, and SHALL remain operable without JavaScript.

#### Scenario: Five choices render five icons

- **WHEN** a rating question with five choices renders as stars
- **THEN** five icons render and selecting the third fills the first three

#### Scenario: Each icon carries its choice name for assistive technology

- **WHEN** a star rating renders
- **THEN** each input is labelled with its choice's name

### Requirement: Stars default to five gold stars and are configurable

The star icon SHALL default to a solid star and its colour to gold. A creator SHALL be able to
choose any Font Awesome icon, any colour, and how many icons the question shows. A question set to
stars without choices SHALL render five numbered steps rather than nothing, resolved at render
time without being written to the question.

#### Scenario: Untouched question shows gold stars

- **WHEN** a rating question is set to stars and neither icon nor colour was ever set
- **THEN** it renders solid stars in gold

#### Scenario: Creator-set icon and colour are used

- **WHEN** the creator sets the icon to a heart and the colour to red
- **THEN** the question renders red hearts

#### Scenario: Stars without choices still render

- **WHEN** a stars question has no choices defined
- **THEN** five numbered stars render and the question's stored choices remain unset

### Requirement: The style never changes what is stored

Every display style SHALL be backed by the same radio group: one selectable value per question,
submitted under the same field name with the choice code as its value and stored in `Answer`
unchanged. Changing a question's style SHALL NOT alter, invalidate or split answers already
collected.

#### Scenario: Submission stores the choice code

- **WHEN** the respondent selects the option with code 4 in any style
- **THEN** the stored answer records choice code 4

#### Scenario: Style switched after responses exist

- **WHEN** a creator switches an answered rating question to another style
- **THEN** the existing answers are unchanged and continue to export under the same column

### Requirement: Cloning preserves the display style

Every question-cloning path — versioning draft clone, editor duplicate, copy/paste — SHALL copy
`display_style` to the new question.

#### Scenario: Draft clone keeps the style

- **WHEN** a published survey containing a rating question with `display_style = "list_pips"` is
  cloned for a draft
- **THEN** the cloned question has `display_style = "list_pips"`
