## MODIFIED Requirements

### Requirement: Violation filtering keeps per-type selection
The Issues control SHALL open a menu listing every violation type present in the
data, grouped into errors and warnings, each with its own count, and SHALL allow
any combination of types to be selected at once (a session matching any selected
type is shown). The control SHALL report how many types are selected and offer a
one-action clear. Replacing the Violations sidebar with a single all-or-nothing
chip is not sufficient. The `empty` type SHALL NOT be offered in the menu: empty
sessions are shown or hidden by the control described in `responses-empty-sessions`,
and when shown they keep their "Empty" badge.

#### Scenario: Selecting one violation type
- **WHEN** the creator opens the Issues menu and ticks "Duplicate"
- **THEN** only duplicate sessions are listed and the control reads "1 selected"

#### Scenario: Selecting several types at once
- **WHEN** the creator additionally ticks "Incomplete"
- **THEN** sessions flagged duplicate **or** incomplete are listed and the control
  reads "2 selected"

#### Scenario: Types with no occurrences are not offered
- **WHEN** a violation type has a zero count for the current survey
- **THEN** the menu omits it rather than offering an empty filter

#### Scenario: Empty is not an Issues entry
- **WHEN** the creator shows empty sessions and opens the Issues menu
- **THEN** the menu has no "Empty sessions" entry, and the empty rows in the table carry the
  "Empty" badge
