# dashboard-layout Specification

## Purpose
How the creator dashboard lays out survey cards, so that it stays usable on a phone whatever the surveys are called.
## Requirements
### Requirement: Survey cards fit the screen whatever the survey name
The system SHALL lay out the dashboard's survey cards so that no card is wider than the
viewport, at any width down to 320 px, whatever the survey names. A survey name with no
break opportunity (for example a snake_case name) SHALL wrap inside its card rather than
widen the card or the grid column, and SHALL NOT widen the other cards.

#### Scenario: Unbreakable name on a phone
- **WHEN** a workspace has a survey named `community_feedback_on_new_cycling_lanes_2026` and the dashboard is opened at 360 px
- **THEN** every card fits inside the viewport, the page has no horizontal scroll, and the long name wraps within its card

