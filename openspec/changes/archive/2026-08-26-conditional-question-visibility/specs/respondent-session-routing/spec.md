# respondent-session-routing Delta Specification

## ADDED Requirements

### Requirement: Section navigation walks the visible chain

Forward and backward navigation between sections SHALL skip sections that are hidden
for the current session under conditional-visibility rules, in both directions. The
stored `next_section`/`prev_section` links SHALL remain untouched — skipping is a
read-time filter. Visibility for navigation SHALL be evaluated against the session's
answers as of the submit being processed. A respondent whose answers satisfy no
section rule in a group of conditioned sections SHALL flow past all of them to the
next unconditional section. Opening a hidden section by direct URL SHALL redirect the
respondent as an unknown-section miss does, not render it.

#### Scenario: Forward navigation skips hidden sections

- **GIVEN** sections "Your area" → "Area 1 count" … "Area 10 count" → "Thanks", each
  area section shown only for its option
- **WHEN** a respondent who answered Area = "Area 7" submits "Your area"
- **THEN** the next rendered section is "Area 7 count"

#### Scenario: Backward navigation skips the same sections

- **WHEN** that respondent presses Back on "Thanks"
- **THEN** the previous rendered section is "Area 7 count", not "Area 10 count"

#### Scenario: No matching rule flows past the fan

- **GIVEN** a respondent whose Area answer shows no area section (uncovered option)
- **WHEN** they submit "Your area"
- **THEN** the next rendered section is "Thanks"

#### Scenario: Direct URL to a hidden section does not render it

- **WHEN** a respondent opens the URL of a section hidden for their session
- **THEN** they are redirected instead of the hidden section rendering
