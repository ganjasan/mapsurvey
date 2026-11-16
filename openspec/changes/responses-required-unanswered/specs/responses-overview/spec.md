## MODIFIED Requirements

### Requirement: KPI strip with daily deltas
The Overview pane SHALL show, for the selected version scope: total responses, completion rate,
median completion time and geo feature count. The completion rate SHALL be the share of shown
responses that are *completed* as defined in `responses-required-unanswered` (every visible
required question answered). Total responses and geo feature count SHALL carry a "+N today"
delta computed in the survey owner's day boundary; a zero delta renders no delta chip. All values
SHALL respect the active version scope and SHALL be computed over the sessions the Responses page
currently shows: with empty sessions hidden (the default, see `responses-empty-sessions`) they are
left out of every KPI, including the completion rate's denominator. No flagged or violations
count SHALL be shown.

#### Scenario: Deltas reflect today's activity
- **WHEN** 7 sessions with at least one answer started today and the Overview renders
- **THEN** the responses KPI shows "+7 today"

#### Scenario: Version scope narrows the KPIs
- **WHEN** the creator selects version v2 in the version scope control
- **THEN** every KPI value and delta is computed over v2 sessions only

#### Scenario: Empty sessions stay out of the KPIs by default
- **WHEN** 4 sessions are in scope, 2 answered every required question and 2 are empty, and
  empty sessions are hidden
- **THEN** total responses reads 2 and completion rate reads 100%

#### Scenario: Optional last page does not lower the rate
- **WHEN** 2 shown sessions answered every required question and one of them skipped the optional
  last page
- **THEN** completion rate reads 100%

### Requirement: Needs-review and latest-responses feeds
The Overview pane SHALL list the most recent sessions ("Latest responses", at least 4) with
per-session: sequence label, start time, duration, geo/answer summary, and validation-status
chip. The feed SHALL draw from the sessions the page currently shows, so hidden empty sessions do
not appear in it. Selecting an entry SHALL open that session's detail surface (see
`responses-detail-drawer`). There SHALL be no "Needs review" block.

#### Scenario: No needs-review block
- **WHEN** some shown sessions have missing required questions
- **THEN** the Overview renders no "Needs review" block and no issue chips

#### Scenario: Hidden empty sessions do not flood the feed
- **WHEN** the scope holds 30 empty sessions and empty sessions are hidden
- **THEN** Latest responses lists none of them

#### Scenario: Feed entry opens detail
- **WHEN** the creator activates a latest-responses entry
- **THEN** the detail surface for that session opens
