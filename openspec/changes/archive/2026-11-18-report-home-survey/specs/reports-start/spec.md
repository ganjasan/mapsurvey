## ADDED Requirements

### Requirement: A blank report started from a survey belongs to it
The system SHALL make a blank report started at the start address with a survey named — the link
"Make a report" on a survey's Responses page and on its dataset — that survey's report, when the
member has the editor role on the survey. Without a survey named the blank report SHALL have no
home survey.

#### Scenario: Blank from Responses
- **WHEN** an editor follows "Make a report" from survey A's Responses page and presses "Blank report"
- **THEN** the new report's home survey is A

#### Scenario: Blank from the Reports list
- **WHEN** an editor presses "New report" on the Reports list
- **THEN** the new report has no home survey
