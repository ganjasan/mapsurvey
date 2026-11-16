## MODIFIED Requirements

### Requirement: Completed-only uses the Responses overview's definition

`completed_only=1` SHALL restrict every format to *completed* sessions as defined in
`responses-required-unanswered` — not empty and every visible required question answered — the
same predicate the Responses overview uses for its "completed" count, through one shared helper,
so the exported row count equals the overview's completed count for the same scope.

#### Scenario: Counts agree
- **WHEN** a survey has 5 clean sessions of which 3 answered every visible required question
- **THEN** `?format=xlsx&completed_only=1` yields 3 rows in `sessions`, and the Responses overview
  shows 3 completed for the same version scope

#### Scenario: Combined with include_all
- **WHEN** a trashed session answered every visible required question and the request has
  `completed_only=1` without `include_all`
- **THEN** that session is absent
