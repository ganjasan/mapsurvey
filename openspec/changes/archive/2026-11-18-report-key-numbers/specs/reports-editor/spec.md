## ADDED Requirements

### Requirement: Key numbers arrive filled and are picked, not typed as tokens
The system SHALL fill a Key numbers block added in the editor to a report with a home survey with
the numbers a drafted report opens with — people who opened, answered and finished the survey, and
the marks on its first map question when it has one — each following the answers. A block added to
a report without a home survey SHALL arrive empty for typed numbers. The editor SHALL offer the
survey's numbers with their current values in a menu, both to add a number and to change a number
that follows the answers, together with a number the author types; and SHALL NOT show token
syntax in the Key numbers block or its settings.

#### Scenario: A filled block on the first click
- **WHEN** an editor adds a Key numbers block to a report of a survey with a map question
- **THEN** the block holds four numbers that follow the answers and the page shows their values, with no notice that the block is left out

#### Scenario: A report without a survey
- **WHEN** an editor adds a Key numbers block to a report without a home survey
- **THEN** the block is empty and takes typed numbers

#### Scenario: The menu of survey numbers
- **WHEN** the editor of a report of a survey is opened
- **THEN** it offers the survey's numbers with their current values and a number to type, and the Key numbers settings name no token

#### Scenario: A number that follows the answers is not a text field
- **WHEN** a Key numbers block holds a number that follows the answers
- **THEN** the canvas marks it as live and shows its value, not its token

#### Scenario: A typed number
- **WHEN** an editor saves a row with a typed value and a label
- **THEN** the block holds it as typed
