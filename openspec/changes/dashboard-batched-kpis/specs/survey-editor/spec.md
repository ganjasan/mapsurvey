## ADDED Requirements

### Requirement: Dashboard card statistics
Each survey card on `/editor/` SHALL show *completed* and *completion %* computed over the
survey's whole version family (the canonical survey plus its archived versions, never the draft
copy), from non-deleted sessions, with a session counted as completed when it answered a
question of its own version's last section — the same numbers the Responses overview reports
for the default "all versions" scope. The dashboard SHALL compute these numbers for all its
cards together, in a number of database queries that does not grow with the number of surveys
listed; it SHALL NOT compute per-session issue flags, which no card shows.

#### Scenario: Card numbers match the Responses overview
- **WHEN** a survey has sessions on its canonical version and on an archived version, some of
  them completed, one deleted, and a preview session on its draft copy
- **THEN** its dashboard card shows the same completed count and completion % as
  `SurveyAnalyticsService(survey).get_overview()`

#### Scenario: Survey with no sessions
- **WHEN** a survey on the dashboard has no sessions
- **THEN** its card shows 0 completed and 0%

#### Scenario: Query count does not grow with the survey list
- **WHEN** the dashboard is rendered for a workspace with 2 surveys and again for one with 8
  surveys of the same shape
- **THEN** both renders run the same number of database queries
