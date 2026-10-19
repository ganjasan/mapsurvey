## MODIFIED Requirements

### Requirement: Dropdown style is scoped to choice questions
Each display style SHALL take effect only on the question types it is defined for:

- `rating`: `default`, `scale_strip`, `list_pips`, `stars`
- `choice`: `default`, `dropdown`, `icon_grid`
- `multichoice`: `default`, `icon_grid`

This one table SHALL be the source for respondent rendering, the editor's save and preview, and import. A stored `display_style` on any other type, or with a value not listed for its type, SHALL be treated as unrecognized and SHALL fall back to that type's default rendering.

#### Scenario: Dropdown on a rating question is ignored
- **WHEN** a rating question somehow carries `display_style = "dropdown"`
- **THEN** it renders using the survey's default rating style

#### Scenario: Dropdown on a multichoice question is ignored
- **WHEN** a multichoice question carries `display_style = "dropdown"`
- **THEN** it renders as the checkbox list

#### Scenario: Icon grid on a text question is ignored
- **WHEN** a text question carries `display_style = "icon_grid"`
- **THEN** it renders as the plain text area
