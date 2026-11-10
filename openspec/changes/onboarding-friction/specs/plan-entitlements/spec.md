## ADDED Requirements

### Requirement: Navigation carries a lock, not a Pro label
A template tag `{% pro_nav_mark org "key" %}` SHALL render the Pro mark of a navigation item (the
app sidebar) from the same state computation as `{% pro_badge %}`: nothing in the `plan`, `trial`
and `startable` states, and in the `locked` state a lock icon with the tooltip "A Pro feature. See
Plan & billing." and no text. Navigation items SHALL use this tag and never `{% pro_badge %}`; a
control that offers or makes a Pro use SHALL keep `{% pro_badge %}`. An unknown key SHALL raise
in tests and render nothing in production, as for `pro_badge`.

#### Scenario: Silent unless locked
- **WHEN** the tag is rendered for `api` on a Pro workspace, on a Free one with a live trial, on a startable Free one, and on a Free one whose owner used their trial elsewhere
- **THEN** it renders nothing, nothing, nothing, and a lock with `data-pro-state="locked"` and no "Pro" text respectively

#### Scenario: Point-of-use marks unchanged
- **WHEN** the API & connections page renders for a startable Free workspace
- **THEN** its heading still carries "Pro · free to try"
