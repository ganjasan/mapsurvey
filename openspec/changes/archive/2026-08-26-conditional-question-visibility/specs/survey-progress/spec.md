# survey-progress Delta Specification

## MODIFIED Requirements

### Requirement: Progress indicator is computed from section linked list

The view SHALL compute the current section index and total section count by traversing
the `prev_section` / `next_section` linked list on `SurveySection`, counting only the
sections visible for the current session under conditional-visibility rules. No new
model fields are required. When `CONDITIONAL_VISIBILITY` is off, or no section carries
a rule, the count SHALL equal the full linked list, preserving prior behaviour.

#### Scenario: Section position derived from linked list

- **WHEN** sections A → B → C → D are linked via `next_section` and none carries a
  visibility rule
- **AND** the user is on section C
- **THEN** `section_current` is 3 and `section_total` is 4

#### Scenario: Hidden sections are excluded from the count

- **GIVEN** sections A → B → C → D where C's rule is not satisfied for this session
- **WHEN** the user is on section D
- **THEN** `section_current` is 3 and `section_total` is 3

#### Scenario: Count updates when a controlling answer changes

- **GIVEN** a session whose answers previously satisfied C's rule
- **WHEN** the user changes the controlling answer so C becomes hidden and navigates
- **THEN** subsequent renders show totals computed over the new visible chain
