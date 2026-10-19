## ADDED Requirements

### Requirement: Icon grid colour controls
While Icon grid is the selected style of a `choice` or `multichoice` question, the question modal SHALL show the question's **Color** field, which colours every tile icon.

The choices table SHALL show a **Color** column next to Icon. Each cell SHALL hold a colour swatch and a control that clears it. A cleared cell SHALL save no `color` for that option, and the option then follows the question colour. As with Icon and Group, the column SHALL be hidden under other styles without losing its values.

#### Scenario: Color field appears with the grid
- **WHEN** the creator switches a choice question's "Display as" to Icon grid
- **THEN** the Color field becomes visible

#### Scenario: Per-option colour saves
- **WHEN** the creator sets one row's colour and saves
- **THEN** that choice entry carries `color`, and rows left cleared carry none
