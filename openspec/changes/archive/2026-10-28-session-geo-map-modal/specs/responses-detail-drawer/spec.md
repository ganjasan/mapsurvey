## ADDED Requirements

### Requirement: The workspace fills the viewport and its regions scroll independently
On viewports where the detail surface sits beside a pane (≥1200px), the Responses workspace SHALL occupy the available viewport height rather than growing with its content, so that the page itself does not scroll. The detail surface SHALL scroll within its own bounds when its content exceeds that height, and the responses table's footer controls (pagination and rows-per-page) SHALL remain within the viewport while the detail surface is open.

#### Scenario: Long response open beside the table
- **WHEN** a creator opens a response whose answers exceed the available height
- **THEN** the detail surface scrolls inside itself, the page does not scroll, and the table footer stays on screen

#### Scenario: Short response
- **WHEN** the open response is short enough to fit
- **THEN** nothing scrolls and the layout is unchanged

#### Scenario: Overlay tiers
- **WHEN** the viewport is below 1200px, where the detail surface is an overlay or full-screen view
- **THEN** the surface keeps its own height rules and this requirement does not constrain the page behind it
