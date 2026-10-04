## MODIFIED Requirements

### Requirement: Geo questions and form layout exclude each other
A `form` section SHALL NOT contain geo questions (`point`, `line`, `polygon`, `spraycan`). The
system SHALL enforce this at question creation/save time and at layout-switch time; there is no
rendering fallback for a geo question inside a form section because the state is unreachable
through the product.

#### Scenario: Geo question rejected in a form section
- **WHEN** a request tries to save a `point` question into a section with `layout = "form"`
- **THEN** the save is refused with an error

#### Scenario: Spraycan question rejected in a form section
- **WHEN** a request tries to save a `spraycan` question into a section with `layout = "form"`
- **THEN** the save is refused with the same error

#### Scenario: Layout switch refused while geo questions exist
- **WHEN** a creator tries to set `layout = "form"` on a section containing a `polygon` question
- **THEN** the change is refused with a message naming the blocking questions
