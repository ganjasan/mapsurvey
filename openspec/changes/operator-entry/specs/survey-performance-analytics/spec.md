# survey-performance-analytics — delta for operator-entry

## ADDED Requirements

### Requirement: Operator sessions are absent from performance analytics
Sessions created by the operator entry form (`source != online`) SHALL write no `SurveyEvent`
rows, and the Perf pane — section funnel, sessions started, completion, durations, referrers and
device breakdowns — SHALL therefore count respondent-link sessions only. A Responses overview that
counts answers SHALL still include them.

#### Scenario: Entered sheets do not move the funnel
- **GIVEN** a survey with 10 online sessions, of which 5 completed
- **WHEN** an operator enters 20 paper sheets to completion
- **THEN** the section funnel still reports 10 started and 5 completed

#### Scenario: Overview counts them
- **WHEN** the Responses overview renders for that survey
- **THEN** the response count includes the 20 entered sessions
