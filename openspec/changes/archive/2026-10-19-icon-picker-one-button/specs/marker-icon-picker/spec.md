## ADDED Requirements

### Requirement: The picker is one button
The icon picker SHALL render as a single button that shows the current icon, or a dashed "+" when the value is empty. The value input SHALL remain in the form, hidden, and SHALL be the field that is submitted. The picker SHALL NOT render a visible text field or a separate browse button. Every value change made through the picker SHALL dispatch an `input` event on the value input.

#### Scenario: One control per choices-table row
- **WHEN** the choices table shows the Icon column
- **THEN** each row's Icon cell contains exactly one visible control, the picker button

#### Scenario: Empty value
- **WHEN** an option has no icon
- **THEN** its picker button shows a dashed "+" and submits an empty value

### Requirement: An icon can be removed
The picker panel SHALL offer a "Remove icon" control while the value is non-empty. While no search query is typed, the first cell of the grid SHALL be a "No icon" cell. Either one SHALL set the value to empty and close the panel.

#### Scenario: Remove clears the value
- **WHEN** the creator opens the picker of an option whose icon is `maki:park` and activates "Remove icon"
- **THEN** the option's value is empty, its button shows "+", and the saved choice has no `icon`

### Requirement: A typed value can be used as is
When the search query is itself a valid icon value (a Font Awesome class such as `fas fa-hiking`, or a `maki:`/`temaki:` name), the panel SHALL offer "Use <value>". Activating it, or pressing Enter in the search box, SHALL set that value. Enter in the search box SHALL NOT submit the surrounding form.

#### Scenario: Pasted class
- **WHEN** the creator types `fas fa-hiking` into the picker's search box and activates "Use fas fa-hiking"
- **THEN** the value becomes `fas fa-hiking`

### Requirement: The panel is placed next to its button
The panel SHALL be at most 560 px wide (the viewport width less 16 px where narrower) and at most 520 px tall. Its size SHALL NOT depend on the input or the table cell. It SHALL be positioned with fixed placement:
- below the button when it fits there;
- otherwise above the button when it fits there;
- otherwise on the side with more room, its height reduced to that room.

It SHALL never cover its own button and SHALL stay inside the viewport. Below 768 px it SHALL be the full-width bottom sheet.

#### Scenario: No room below
- **WHEN** the picker is opened from a row near the bottom of the viewport
- **THEN** the panel opens above the button, entirely on screen, without overlapping the button
