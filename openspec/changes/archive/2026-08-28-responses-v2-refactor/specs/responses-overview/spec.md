# responses-overview — Delta Specification

## ADDED Requirements

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
delta renders no delta chip. All values SHALL respect the active version scope.

#### Scenario: Deltas reflect today's activity
- **WHEN** 7 sessions started today and the Overview renders
- **THEN** the responses KPI shows "+7 today"

#### Scenario: Version scope narrows the KPIs
- **WHEN** the creator selects version v2 in the version scope control
- **THEN** every KPI value and delta is computed over v2 sessions only

### Requirement: Needs-review and latest-responses feeds
The Overview pane SHALL list sessions with validation violations ("Needs review") and the most
recent sessions ("Latest responses", at least 4) with per-session: sequence label, start time,
duration, geo/answer summary, and status chip. Selecting an entry SHALL open that session's detail
surface (see `responses-detail-drawer`). When there are no violations the Needs-review block SHALL
be omitted, not rendered empty.

#### Scenario: Violation surfaces in the feed
- **WHEN** one session is flagged as an empty session
- **THEN** Needs review lists that session with an "empty" status chip and the flagged KPI shows 1

#### Scenario: Feed entry opens detail
- **WHEN** the creator activates a latest-responses entry
- **THEN** the detail surface for that session opens

### Requirement: Overview empty state sells the next action
When the survey has zero sessions in scope, the Overview pane SHALL replace KPI/feed content with
an empty state containing a share action and a respondent-preview action, and SHALL NOT render
zero-filled KPI cards.

#### Scenario: Zero responses
- **WHEN** a published survey with no sessions opens the Responses tab
- **THEN** the Overview shows the "No responses yet" state with Share and Preview actions

### Requirement: Overview map thumbnail and trend
The Overview pane SHALL render a non-interactive (or view-only) map thumbnail of current geo
features linking to the Map pane, and a responses-per-day trend for the last 7 days. Surveys with
no geo questions SHALL omit the map thumbnail block.

#### Scenario: Thumbnail opens the Map pane
- **WHEN** the creator activates the map thumbnail or its "Open Map" action
- **THEN** the Map pane becomes active

#### Scenario: No geo questions
- **WHEN** the survey has no point/line/polygon questions
- **THEN** the Overview renders without a map thumbnail block
