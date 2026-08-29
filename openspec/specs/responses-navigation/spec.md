# responses-navigation Specification

## Purpose
TBD - created by archiving change responses-v2-refactor. Update Purpose after archive.
## Requirements
### Requirement: Flat pane set replaces stacked navigation
When `RESPONSES_V2` is on, the Responses tab SHALL present exactly one pane-selection level:
Overview, Map, Responses, Charts, Performance. The Data/Performance sub-tab row and the per-pane
Table/Map/Charts tab bars SHALL NOT be rendered. The Responses pane item SHALL show an unread
badge when violations exist.

#### Scenario: One navigation level on desktop
- **WHEN** the Responses tab renders at ≥1200px
- **THEN** the five pane items are the only pane-level navigation and no pane contains its own
  Table/Map/Charts tab bar

#### Scenario: Violations badge
- **WHEN** at least one session has a validation violation
- **THEN** the Responses pane item carries a count badge

### Requirement: Form-factor collapse of the pane set
The pane set SHALL collapse per form factor: at ≥1200px all five panes plus the Split view
control; at 768–1199px all five panes without Split view; below 768px a bottom bar with
Overview, Map, Responses, Performance, where Charts content lives inside Overview (each question
card links to its full chart). The active pane SHALL be URL-hash-addressable (`#overview`,
`#map`, `#responses`, `#charts`, `#performance`) by one router shared across form factors.

#### Scenario: Tablet hides Split view
- **WHEN** the viewport is 900px wide
- **THEN** all five panes are selectable and no Split view control renders

#### Scenario: Phone bottom bar
- **WHEN** the viewport is below 768px
- **THEN** the bottom bar shows Overview/Map/Responses/Performance and no Charts item

#### Scenario: Hash routing works from a shared link
- **WHEN** a creator opens the page with `#performance` on any form factor
- **THEN** the Performance pane is active

### Requirement: RESPONSES_V2 kill switch
A `RESPONSES_V2` environment setting SHALL select between the v2 template and the byte-identical
legacy template at the view level. With the switch off, the legacy Responses tab SHALL render
exactly as before this change.

#### Scenario: Switch off serves legacy
- **WHEN** `RESPONSES_V2` is false and the Responses tab is requested
- **THEN** the pre-change template renders with its original navigation

#### Scenario: Switch on serves v2
- **WHEN** `RESPONSES_V2` is true (default)
- **THEN** the v2 pane structure renders

### Requirement: No whole-page horizontal scroll
On every form factor the Responses tab SHALL NOT produce document-level horizontal overflow.
Wide content (the response table) SHALL scroll only inside its own container.

#### Scenario: Phone viewport stays 1:1
- **WHEN** the page renders at 390px width with all panes visited
- **THEN** `document.scrollingElement.scrollWidth` equals the viewport width

### Requirement: Performance KPIs are labeled as tracked-visit metrics
The Performance pane SHALL label its session KPIs so they cannot be read as response counts
(e.g. "sessions started (tracked visits)"), and SHALL NOT render alarm styling for funnel drop
rates when the tracked sample is below a minimum threshold (default 20 tracked sessions); below
threshold it SHALL state that the sample is too small instead.

#### Scenario: Tracked-visit labeling
- **WHEN** the Performance pane renders with 1 tracked session while the survey has 65 responses
- **THEN** the started-sessions KPI is explicitly labeled as tracked visits

#### Scenario: Small-sample funnel
- **WHEN** fewer than 20 tracked sessions exist
- **THEN** the section funnel shows a small-sample notice instead of percentage drop alarms

