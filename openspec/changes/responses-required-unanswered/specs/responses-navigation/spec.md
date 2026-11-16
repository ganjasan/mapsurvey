## MODIFIED Requirements

### Requirement: Flat pane set replaces stacked navigation
When `RESPONSES_V2` is on, the Responses tab SHALL present exactly one pane-selection level:
Overview, Map, Responses, Charts, Performance. The Data/Performance sub-tab row and the per-pane
Table/Map/Charts tab bars SHALL NOT be rendered. The Responses pane item SHALL carry no
violations badge.

#### Scenario: One navigation level on desktop
- **WHEN** the Responses tab renders at ≥1200px
- **THEN** the five pane items are the only pane-level navigation and no pane contains its own
  Table/Map/Charts tab bar

#### Scenario: No badge for missing required questions
- **WHEN** some sessions have missing required questions
- **THEN** the Responses pane item carries no count badge
