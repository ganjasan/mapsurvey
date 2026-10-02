# responses-overview Specification

## Purpose
TBD - created by archiving change responses-v2-refactor. Update Purpose after archive.
## Requirements
### Requirement: Overview is the default Responses pane
The Responses tab SHALL open on the Overview pane by default on every form factor when
`RESPONSES_V2` is on. A stored pane preference (URL hash or persisted layout) MAY override the
default, but a first visit with no stored state SHALL land on Overview.

#### Scenario: First visit lands on Overview
- **WHEN** a creator opens `/editor/surveys/<uuid>/analytics/` with no stored layout and no URL hash
- **THEN** the Overview pane is active and its KPI strip, map thumbnail, trend and feeds are rendered

#### Scenario: Deep link overrides the default
- **WHEN** the page is opened with `#responses` (or `#map`, `#charts`, `#performance`)
- **THEN** that pane is active instead of Overview

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

### Requirement: Overview map thumbnail and trend
The Overview pane SHALL render a non-interactive (or view-only) map thumbnail of current geo
features linking to the Map pane, and a responses-per-day trend for the last 7 days. Surveys with
no geo questions SHALL omit the map thumbnail block. The thumbnail SHALL be mounted through the
shared editor map helper and SHALL add its features and fit them only once its container has a
size, rather than after a fixed delay.

#### Scenario: Thumbnail opens the Map pane
- **WHEN** the creator activates the map thumbnail or its "Open Map" action
- **THEN** the Map pane becomes active

#### Scenario: No geo questions
- **WHEN** the survey has no point/line/polygon questions
- **THEN** the Overview renders without a map thumbnail block

#### Scenario: Thumbnail fits its features after layout, not after a timer
- **WHEN** the Overview pane is the landing pane or is returned to from another pane
- **THEN** the thumbnail shows the features fitted to view, with no dependency on a delay chosen by hand

#### Scenario: Built while its pane was hidden
- **WHEN** the thumbnail's map is constructed while its container measures 0×0 and the container is laid out later
- **THEN** the helper SHALL notice the container's real size, and the thumbnail SHALL draw and fit the features

#### Scenario: Container already laid out at mount
- **WHEN** the container already has a size when the map is mounted, so the ready callback runs at once
- **THEN** nothing after mounting SHALL reset the view, and the thumbnail SHALL stay fitted to the features

