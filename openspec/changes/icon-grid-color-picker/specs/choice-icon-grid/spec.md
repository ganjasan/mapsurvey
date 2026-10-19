## ADDED Requirements

### Requirement: Tile icons take the option colour, then the question colour
A tile's icon SHALL be drawn in the colour picked by the first matching rule:

1. the option's own `color`, when it is a valid `#RRGGBB`;
2. otherwise the question's `color`, unless that is the model default `#000000`;
3. otherwise the grid's default glyph grey.

The colour SHALL reach the glyph only through the marker-icon helper's `color` argument. It SHALL NOT tint the tile's label, border or highlight.

#### Scenario: Question colour paints every icon
- **WHEN** an icon-grid question has `color = "#16a34a"` and no option colours
- **THEN** every tile icon is drawn with `#16a34a`

#### Scenario: Option colour overrides the question colour
- **WHEN** one option has `color = "#dc2626"` on a question coloured `#16a34a`
- **THEN** that option's icon is `#dc2626` and the others stay `#16a34a`

#### Scenario: Default colour keeps the grey
- **WHEN** an icon-grid question keeps the default `color = "#000000"` and no option colours
- **THEN** the icons carry no inline colour and render in the grid's default grey
