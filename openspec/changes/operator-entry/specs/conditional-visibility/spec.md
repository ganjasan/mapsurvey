# conditional-visibility — delta for operator-entry

## MODIFIED Requirements

### Requirement: Hidden items are not applicable server-side

The server SHALL treat a hidden question as not applicable regardless of what the client
submits: a posted answer for a question hidden under the submitted answer state SHALL be
discarded, a hidden question's `required` SHALL never block progression, and after each
section submit the session's stored answers to questions hidden under the new answer
state SHALL be deleted (including geo answers, whose sub-answers are deleted with them).
"Hidden" SHALL include an item whose effective audience (spec `question-audience`) excludes the
surface being evaluated, so the same discard, purge and never-required rules apply to an
operator-only question on the respondent page and to a respondent-only question on the entry
form. When the `CONDITIONAL_VISIBILITY` kill switch is off, all rule-conditioned items SHALL be
treated as visible and rules SHALL have no respondent-facing effect; audience SHALL still apply.

#### Scenario: Tampered answer to a hidden question is discarded

- **WHEN** a POST includes a value for a question hidden under the submitted answers
- **THEN** no Answer row is stored for that question

#### Scenario: Changing the controlling answer purges the abandoned branch

- **GIVEN** a respondent answered questions inside section "Area 7 count"
- **WHEN** they go back, change Area to "Area 4", and submit
- **THEN** the stored answers inside "Area 7 count" are deleted from the session

#### Scenario: Hidden required question does not block completion

- **GIVEN** a required question hidden for this respondent
- **WHEN** the respondent submits the section and finishes the survey
- **THEN** the session completes without an answer to that question

#### Scenario: Operator-only question posted by a respondent is discarded

- **GIVEN** a question with audience `operators`
- **WHEN** a respondent's POST includes a value for its code
- **THEN** no Answer row is stored for that question

#### Scenario: Kill switch restores pre-change behaviour

- **WHEN** `CONDITIONAL_VISIBILITY` is set to False
- **THEN** every rule-conditioned question and section renders for every respondent and no stored
  answers are rule-purged
- **AND** an `operators` question is still absent from the respondent page
