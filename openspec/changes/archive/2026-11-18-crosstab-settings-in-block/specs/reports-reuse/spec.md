## MODIFIED Requirements

### Requirement: A Compare block shows one question in two rounds
The system SHALL offer a block that shows, for one question code present in two surveys of the
workspace, the share of each answer in both, with the number of people who answered in each. A
group smaller than the report's threshold SHALL be masked in its own round. The block SHALL be
refused when the other survey has no question with that code and a comparable type. The block
library SHALL add it in one click with the first question that has a comparable twin in another
survey; the block's settings SHALL change the question and the other survey.

#### Scenario: Two rounds side by side
- **WHEN** an editor adds a Compare block of `PRIO` with a second survey where the answers differ
- **THEN** the page shows both surveys' names, how many people answered in each, and each option's share in each

#### Scenario: Small groups
- **WHEN** an option was chosen by fewer people than the threshold in one round
- **THEN** that round's cell reads "<K" with no share, and the other round's cell is shown

#### Scenario: No such question in the other survey
- **WHEN** an editor adds a Compare block naming a survey without that question code, or sets an existing block to one
- **THEN** it is refused with a message and nothing changes

#### Scenario: One click
- **WHEN** an editor clicks the Compare tile of a survey whose `PRIO` question has a twin in an earlier round
- **THEN** the report gets a Compare block of `PRIO` with that round, without a form in the library
