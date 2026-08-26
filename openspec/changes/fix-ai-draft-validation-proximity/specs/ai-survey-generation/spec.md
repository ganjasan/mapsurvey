## ADDED Requirements

### Requirement: Field-level presentation of generate validation errors
When the generate action fails form validation, the errors SHALL be presented at their
source: each offending field SHALL be visually marked (error border) and SHALL show its
error message directly adjacent to the field (e.g. "This field is required." under the
goal textarea). The first offending field SHALL be scrolled into view and focused. An
offending field inside the collapsed "Add details (optional)" disclosure SHALL force the
disclosure open before being marked. Field marks and messages SHALL clear when the
creator edits the marked field, and all previous marks SHALL clear at the start of the
next generate attempt. A detached summary banner SHALL NOT be the only presentation of a
field-level error; the `#generation-slot` card remains only for failures without a field
anchor (provider not configured, or an error whose field cannot be resolved on the page).
The mobile wizard's draft-path pre-check SHALL use the same presentation (mark, message,
clear-on-input) for the empty goal, not a bare border color.

#### Scenario: Empty goal on desktop generate
- **WHEN** an editor clicks "Generate draft" with an empty goal field
- **THEN** the goal textarea is marked with an error border, "This field is required." appears directly under it, the field is scrolled into view and focused, and no error card is shown at the bottom of the column

#### Scenario: Error in a collapsed disclosure field
- **WHEN** validation fails for a field inside the collapsed "Add details (optional)" disclosure
- **THEN** the disclosure is opened and the field is marked with its message adjacent

#### Scenario: Marks clear on input
- **WHEN** the creator types into a field marked with a validation error
- **THEN** that field's error border and message are removed

#### Scenario: Non-field failure keeps the slot card
- **WHEN** the generate action fails for a reason with no field anchor (e.g. provider not configured)
- **THEN** the existing `#generation-slot` card presentation is used

#### Scenario: Wizard empty-goal pre-check uses the same presentation
- **WHEN** a creator on the mobile wizard taps the step-1 draft button with an empty goal
- **THEN** the goal field is marked and shows "This field is required." adjacent, the wizard stays on the goal step, and the mark clears once the creator types

### Requirement: Wizard step-1 draft button signals a next step
On the mobile create wizard, the step-1 draft-path primary button SHALL be labeled to
communicate that a further step follows (label: "✨ Next — choose the place") rather than
implying immediate survey creation. The map-step submit button SHALL keep its
"✨ Create draft survey" label.

#### Scenario: Step-1 draft button copy
- **WHEN** the create page renders the mobile wizard goal step with AI available
- **THEN** the draft-path primary button reads "✨ Next — choose the place" and the map step's submit button reads "✨ Create draft survey" after choosing the draft path
