## MODIFIED Requirements

### Requirement: Stars default to five gold stars and are configurable

The star icon SHALL default to a solid star and its colour to gold. A creator SHALL be able to
choose any icon the marker icon catalog offers (a Font Awesome class or a `maki:`/`temaki:`
value), any colour, and how many icons the question shows. The icon SHALL be drawn through the
shared marker icon resolver, so a map-set value renders as an SVG glyph and a Font Awesome value
as before. A question set to stars without choices SHALL render five numbered steps rather than
nothing, resolved at render time without being written to the question.

#### Scenario: Untouched question shows gold stars

- **WHEN** a rating question is set to stars and neither icon nor colour was ever set
- **THEN** it renders solid stars in gold

#### Scenario: Creator-set icon and colour are used

- **WHEN** the creator sets the icon to a heart and the colour to red
- **THEN** the question renders red hearts

#### Scenario: Map-set icon renders as SVG stars

- **WHEN** the creator sets the icon to `maki:star` and the colour to blue
- **THEN** each step renders an SVG glyph from the Maki sprite filled blue, and selecting the third fills the first three

#### Scenario: Stars without choices still render

- **WHEN** a stars question has no choices defined
- **THEN** five numbered stars render and the question's stored choices remain unset
