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

### Requirement: Map pane empty state names the actual gap
When the Responses Map pane has no features to draw, it SHALL distinguish a survey with no
point/line/polygon questions ("No geo questions in this survey", with an action to add one)
from a survey whose geo questions have no answers yet ("No map answers yet", with no editor
action). The distinction SHALL hold on both the v2 and the legacy dashboard.

#### Scenario: Geo question without answers
- **WHEN** the survey has a point question and no answers
- **THEN** the Map pane says "No map answers yet" and does not claim there are no geo questions

#### Scenario: No geo question
- **WHEN** the survey has only non-geo questions
- **THEN** the Map pane says "No geo questions in this survey" and offers "Add a map question"

### Requirement: The response table reads the same whichever version header opens it
The response table SHALL key its question columns on the lineage representative of each
question (the canonical version's question, or the newest archived one), so that a table
opened from a draft copy, an archived version or the canonical survey shows the same
columns with the same cells for the same scope.

#### Scenario: Table opened from a draft copy
- **WHEN** a creator opens Responses on the draft copy of a published survey with answers
- **THEN** each answer appears in its question's column, exactly as on the published survey's Responses tab

### Requirement: Objects-on-the-map questions have no response-table column
The response table SHALL NOT show a column for a `layer_objects` question: its answers are
per object on its sub-questions (shown in the per-object table and the export's objects
sheet), and a display-only one collects nothing.

#### Scenario: Layer question in a section
- **WHEN** a section has a text question and an Objects question bound to a layer
- **THEN** the response table has a column for the text question only

### Requirement: Session timing lives on the session row
`SurveySession.last_activity_at` SHALL be written on every section submit and on the
page-leave beacon; `SurveySession.end_datetime` SHALL be set when the respondent reaches the
thanks page (first completion wins). The response table's Duration SHALL read
`end_datetime − start_datetime` for completed sessions and `last_activity_at −
start_datetime`, marked with a trailing "+", for sessions that left; it SHALL NOT depend on
the event log. Both timestamps SHALL ride the responses ZIP export and import. Existing rows
are backfilled once from the event log where one exists.

#### Scenario: Completed session
- **WHEN** a respondent submits the last section and lands on the thanks page
- **THEN** the session has `end_datetime`, and Duration shows the elapsed time without a "+"

#### Scenario: Abandoned session
- **WHEN** a respondent submits one section and closes the tab (page-leave beacon)
- **THEN** `last_activity_at` is set, `end_datetime` is not, and Duration shows the elapsed time with a "+"

#### Scenario: Imported responses
- **WHEN** responses are imported from a ZIP written after this change
- **THEN** the imported sessions keep their timing and show a Duration

