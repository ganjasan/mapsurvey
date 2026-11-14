## MODIFIED Requirements

### Requirement: Clean-session data source on the canonical survey
Aggregates, geo features and the response counter SHALL be computed only from sessions that are not
deleted, not marked invalid or on hold, and not empty (a session with no top-level answer, as
defined in `responses-empty-sessions`), aggregated against the canonical survey, through the shared
session scope (`session-scope`). The same scope SHALL apply to Site results blocks, so the public
page, a Site block and the Responses headline count the same answered responses.

#### Scenario: Deleted and invalid sessions excluded
- **WHEN** a survey has sessions that are deleted or marked invalid
- **THEN** those sessions contribute to neither the counts, charts, nor map of the public page

#### Scenario: Empty sessions are not counted
- **WHEN** a survey has 5 answered clean sessions and 2 clean sessions without any answer
- **THEN** the public page's response counter shows 5

#### Scenario: Aggregation spans versions via canonical survey
- **WHEN** a survey has multiple published versions sharing one canonical survey
- **THEN** the public page aggregates responses across versions and the response count does not reset on a version transition

#### Scenario: Frozen page keeps its snapshot
- **WHEN** a page was frozen before this rule changed
- **THEN** it keeps showing the counts stored in its snapshot until the creator refreshes it
