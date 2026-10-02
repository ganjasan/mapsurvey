## MODIFIED Requirements

### Requirement: KPI strip with daily deltas
The Overview pane SHALL show, for the selected version scope: total responses, completion rate,
median completion time, geo feature count, and flagged (violations) count. Total responses and geo
feature count SHALL carry a "+N today" delta computed in the survey owner's day boundary; a zero
delta renders no delta chip. All values SHALL respect the active version scope and SHALL be
computed over the sessions the Responses page currently shows: with empty sessions hidden (the
default, see `responses-empty-sessions`) they are left out of every KPI, including the completion
rate's denominator.

#### Scenario: Deltas reflect today's activity
- **WHEN** 7 sessions with at least one answer started today and the Overview renders
- **THEN** the responses KPI shows "+7 today"

#### Scenario: Version scope narrows the KPIs
- **WHEN** the creator selects version v2 in the version scope control
- **THEN** every KPI value and delta is computed over v2 sessions only

#### Scenario: Empty sessions stay out of the KPIs by default
- **WHEN** 4 sessions are in scope, 2 answered the last section and 2 are empty, and empty sessions
  are hidden
- **THEN** total responses reads 2 and completion rate reads 100%

### Requirement: Needs-review and latest-responses feeds
The Overview pane SHALL list sessions with validation violations ("Needs review") and the most
recent sessions ("Latest responses", at least 4) with per-session: sequence label, start time,
duration, geo/answer summary, and status chip. Both feeds SHALL draw from the sessions the page
currently shows, so hidden empty sessions appear in neither. Selecting an entry SHALL open that
session's detail surface (see `responses-detail-drawer`). When there are no violations the
Needs-review block SHALL be omitted, not rendered empty.

#### Scenario: Violation surfaces in the feed
- **WHEN** one shown session is flagged as a duplicate
- **THEN** Needs review lists that session with a "duplicate" status chip and the flagged KPI
  shows 1

#### Scenario: Hidden empty sessions do not flood the feed
- **WHEN** the scope holds 30 empty sessions and empty sessions are hidden
- **THEN** neither Needs review nor Latest responses lists any of them, and the flagged KPI does
  not count them

#### Scenario: Feed entry opens detail
- **WHEN** the creator activates a latest-responses entry
- **THEN** the detail surface for that session opens

### Requirement: Overview empty state sells the next action
When the survey has zero shown sessions in scope, the Overview pane SHALL replace KPI/feed content
with an empty state containing a share action and a respondent-preview action, and SHALL NOT render
zero-filled KPI cards. When the scope holds hidden empty sessions, the empty state SHALL also state
how many people opened the survey without answering and offer the control that shows them.

#### Scenario: Zero responses
- **WHEN** a published survey with no sessions opens the Responses tab
- **THEN** the Overview shows the "No responses yet" state with Share and Preview actions

#### Scenario: Only empty sessions
- **WHEN** every one of 12 sessions in scope is empty and empty sessions are hidden
- **THEN** the Overview shows the "No responses yet" state with Share and Preview actions and the
  line "12 opened without answering" with a Show control
