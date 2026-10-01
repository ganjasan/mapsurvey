## ADDED Requirements

### Requirement: Showcase order set by staff

Published stories SHALL be listed on the landing carousel and on `/stories/` by the `position`
staff set in the admin, lowest first; stories without a position SHALL follow, newest first.
Re-installing a story with `seed_story` SHALL NOT change its position.

#### Scenario: Owner puts three stories first
- **WHEN** staff give Olney position 1, Whitehouse 2 and Remington 3
- **THEN** the carousel and `/stories/` start with Olney, Whitehouse, Remington, followed by the other published stories newest first
