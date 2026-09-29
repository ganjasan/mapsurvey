## MODIFIED Requirements

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
