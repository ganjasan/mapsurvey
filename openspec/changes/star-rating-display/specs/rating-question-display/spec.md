## ADDED Requirements

### Requirement: A rating question offers three display styles

A `rating` question SHALL be renderable as a compact numbered strip, as a labelled list, or as a
row of icons ("stars"). The style SHALL be selectable per question and as a survey-wide default,
and a question with no style of its own SHALL inherit the survey-wide default.

#### Scenario: Per-question style wins over the survey default

- **WHEN** a rating question has `display_style = 'stars'` in a survey whose default is
  `scale_strip`
- **THEN** it renders as stars

#### Scenario: Survey-wide default applies to an unset question

- **WHEN** a rating question has no display style of its own and the survey default is `stars`
- **THEN** it renders as stars

### Requirement: A star rating renders one icon per choice

The star style SHALL render one icon per defined choice, filled from the first icon up to and
including the respondent's selection, and SHALL remain operable without JavaScript.

#### Scenario: Five choices render five icons

- **WHEN** a rating question with five choices renders as stars
- **THEN** five icons are shown
- **AND** selecting the third fills the first three

#### Scenario: Each icon carries its choice name for assistive technology

- **WHEN** a star rating renders
- **THEN** each input is labelled with its choice's name

### Requirement: Stars default to five gold stars and are configurable

The star icon SHALL default to a solid star and its colour to gold. A creator SHALL be able to
choose any Font Awesome icon, any colour, and how many icons the question shows.

#### Scenario: Untouched question shows gold stars

- **WHEN** a rating question is set to the star style and neither icon nor colour was ever set
- **THEN** it renders solid stars in gold

#### Scenario: Creator-set icon and colour are used

- **WHEN** the creator sets the icon to a heart and the colour to red
- **THEN** the question renders red hearts

#### Scenario: The count follows the choices

- **WHEN** the creator sets the number of stars to seven in the editor
- **THEN** the question's choices become seven and seven icons render

### Requirement: The display style never changes what is stored

A rating answer SHALL be stored in `Answer.selected_choices` regardless of the style that
rendered it, and changing an existing question's style SHALL NOT alter, invalidate or split
answers already collected.

#### Scenario: Same answer through two styles

- **WHEN** a respondent selects the third choice on a star rating and another selects the third
  choice on the same question rendered as a strip
- **THEN** both answers are stored identically

#### Scenario: Style switched after responses exist

- **WHEN** a creator switches a rating question with collected answers to the star style
- **THEN** the existing answers are unchanged and continue to export under the same column
