## ADDED Requirements

### Requirement: Display as for choice and multichoice offers Icon grid
The question modal's "Display as" control SHALL be visible for the `choice`, `multichoice` and `rating` input types. For `choice` it SHALL offer List (the default), Dropdown and Icon grid. For `multichoice` it SHALL offer List (the default) and Icon grid. Each option SHALL be shown as a card with a small preview thumbnail. The picked value SHALL persist to `Question.display_style`. Switching it SHALL update the "Respondent sees" preview without saving.

#### Scenario: Multichoice shows two cards
- **WHEN** the creator selects input type `multichoice` in the question modal
- **THEN** "Display as" shows the List and Icon grid cards, with List selected for a new question

#### Scenario: Icon grid persists
- **WHEN** the creator picks Icon grid on a choice question and saves
- **THEN** the question's `display_style` is `icon_grid`

### Requirement: Choices table has Icon and Group columns for the icon grid
While Icon grid is the selected style, the choices table SHALL show two extra columns:

- an Icon column with the marker icon picker on every row, including rows added later;
- a Group column with a free-text input.

Under any other style both columns SHALL be hidden. Their values SHALL stay in the form, so switching back to Icon grid restores them. The values SHALL be saved as the choice's `icon` and `group`.

#### Scenario: Columns appear with the style
- **WHEN** the creator switches "Display as" from List to Icon grid
- **THEN** the Icon and Group columns appear in the choices table

#### Scenario: Picker on a new row
- **WHEN** the creator adds a choice row while Icon grid is selected and opens its icon picker
- **THEN** the picker opens with the catalog, and the picked value fills that row's Icon cell

#### Scenario: Switching away keeps the values
- **WHEN** the creator fills icons, switches to List and back to Icon grid without saving
- **THEN** the icons are still in their cells
