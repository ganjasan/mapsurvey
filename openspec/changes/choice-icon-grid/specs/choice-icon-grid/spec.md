## ADDED Requirements

### Requirement: Icon grid renders one tile per option
When a `choice` or `multichoice` question has `display_style = "icon_grid"`, the respondent form SHALL render one tile per option, in stored order, instead of the list. Each tile SHALL show the option's icon above its label in the respondent's language. Each tile SHALL wrap the option's native radio (`choice`) or checkbox (`multichoice`) input, so that the submitted value, the required check and keyboard operation are those of the list rendering. Selected tiles SHALL be visibly highlighted.

#### Scenario: Grid submits the same value as the list
- **WHEN** a respondent taps the tile "Playground" (code 4) of an icon-grid choice question and submits the section
- **THEN** the stored answer references code 4, identically to a list submission

#### Scenario: Multichoice tiles toggle independently
- **WHEN** a respondent taps "Bench" and then "Tree" on an icon-grid multichoice question
- **THEN** both tiles are highlighted and both codes are stored on submit

#### Scenario: Required grid blocks the forward button
- **WHEN** a required icon-grid question is left untouched and the section is submitted
- **THEN** the section is not submitted and the question is marked as missing, exactly as an unanswered list question is

#### Scenario: Keyboard selects a tile
- **WHEN** a respondent tabs into an icon-grid choice question and presses an arrow key
- **THEN** the next option becomes checked and its tile highlighted, as with native radios

### Requirement: Icons render through the marker icon helper
A tile's icon SHALL be drawn from the option's `icon` value by the marker-icon helper (`{% marker_icon %}`), never from hand-built markup. If an option's `icon` is empty, missing, or not a known value of the catalog's sets, its tile SHALL render with the label only and no placeholder pin.

#### Scenario: Map-set icon on a tile
- **WHEN** an option has `icon = "maki:playground"`
- **THEN** its tile contains the sprite `<svg><use>` the marker-icon helper produces for that value

#### Scenario: Unknown icon falls back to the label
- **WHEN** an option has `icon = "maki:not-a-real-icon"`
- **THEN** its tile shows the label and no icon element

### Requirement: Consecutive options with the same group share a heading
If an option's `group` value (trimmed, non-empty) equals the previous option's, both SHALL render in the same run of tiles. Each run with a non-empty group SHALL get one small heading showing the group text, escaped as plain text. If no option has a group, the grid SHALL render as one run with no heading.

#### Scenario: Three groups render as three headed runs
- **WHEN** a question has 17 options with icons, grouped in order as "Nature" ×6, "Play" ×5 and "Services" ×6
- **THEN** the grid shows three headings, "Nature", "Play" and "Services", each above its own tiles

#### Scenario: No groups means a flat grid
- **WHEN** no option of an icon-grid question has a group
- **THEN** the grid renders as one run with no heading

#### Scenario: Group text is not markup
- **WHEN** an option's group is `<b>Parks</b>`
- **THEN** the heading shows the literal text `<b>Parks</b>`

### Requirement: Single-choice grid collapses to the chosen row
For a `choice` question in the icon grid, choosing a tile SHALL collapse the grid to the visual row that holds the chosen tile. The other tiles on that row SHALL stay visible, and a "Show all options" control SHALL appear. Activating "Show all options" SHALL expand the full grid. A later change of selection SHALL collapse the grid again around the new choice. A grid rendered with a stored answer SHALL appear collapsed once it is visible. A `multichoice` grid SHALL never collapse. If the rows cannot be measured, the grid SHALL stay expanded.

#### Scenario: Picking collapses to the line
- **WHEN** a respondent picks a tile on the second row of a 17-tile grid in a pop-up
- **THEN** only the tiles of that row remain visible, together with "Show all options"

#### Scenario: Show all expands
- **WHEN** the respondent activates "Show all options" on a collapsed grid
- **THEN** every tile and group heading is visible again

#### Scenario: Re-pick collapses again
- **WHEN** the respondent, with the grid expanded, picks a tile on another row
- **THEN** the grid collapses to that row

#### Scenario: Multichoice stays open
- **WHEN** a respondent checks a tile on an icon-grid multichoice question
- **THEN** the full grid stays visible

### Requirement: Icon grid works on every respondent surface and in the preview
The icon grid SHALL render and behave the same way on every surface: the section form, the sub-question pop-ups of geo features and layer objects (including pop-ups opened after page load), and the editor's "Respondent sees" preview (`editor_question_preview_live` and the saved-question preview).

#### Scenario: Grid in a geo pop-up
- **WHEN** an icon-grid choice is a sub-question of a point question and the respondent places a point
- **THEN** the pop-up shows the tiles, and picking one collapses the grid there

#### Scenario: Preview matches the respondent page
- **WHEN** the creator selects Icon grid in the question modal without saving
- **THEN** the "Respondent sees" frame shows the same tiles, icons and group headings a respondent would see

### Requirement: Write-in option inside a grid
If an icon-grid question has an option flagged `other`, that option's tile SHALL behave like any other tile. The write-in text field SHALL render once, beneath the grid. It SHALL be shown while that option is selected and stored under the same rules as in the list rendering.

#### Scenario: Picking the write-in tile shows the text field
- **WHEN** a respondent picks the tile flagged as "Other"
- **THEN** the write-in field beneath the grid appears, and its text is stored with the answer on submit
