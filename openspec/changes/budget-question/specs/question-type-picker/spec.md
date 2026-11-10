## ADDED Requirements

### Requirement: The budget type in the picker, the price in the geo dialog

The picker SHALL offer `budget` ("Budget", `fa-coins`) in the Questions group after `ranking`.
Picking it SHALL show a Budget block in the dialog (mode cards; total, unit, symbol, step; rule
for Split; minimum items; source) and extend the Choices table with Description and Cost
columns; with source `layer` the table is replaced by a layer picker and a cost property picker
reading `SurveyMapLayer.property_names`, and the switch carries the Pro badge for `budget_map`.
The dialog of a geo question that sits in a budget group SHALL show a Price block under "Places
per respondent" — amount in the group's unit, and "per" narrowed to what the type can measure
(mark; metre of the line for lines; square metre of the area for polygons and spray). The live
preview SHALL render the respondent block of the mode. The "New question" picker (never the
type-switch picker of an existing question or a sub-question picker) SHALL also offer a
**Budget group** card in the Map questions group — an ACTION, not an input type
(`question_types.PICKER_ACTIONS`): clicking it posts `budget=1` and the typed name to the group
endpoint, which creates a group with a starting budget and opens the group dialog. The card
is greyed out with the geo types' reason on a section without a map; it carries no Pro badge
(budget groups are free).

#### Scenario: Budget sits with the questions

- **WHEN** a creator opens the picker on any section
- **THEN** "Budget" appears in the Questions group; the Map questions group gains only the Budget group card

#### Scenario: Switching to Projects demands costs

- **WHEN** the creator switches the mode card from Split to Projects
- **THEN** the Cost column becomes required and an item without one is marked before Save

#### Scenario: Price per is narrowed by type

- **WHEN** the creator opens a line question inside a budget group
- **THEN** the Price block offers "mark" and "metre of the line" and hides "square metre of the area"

#### Scenario: Budget group card creates a group

- **WHEN** a creator types "Park improvements" in the New question dialog of a map section and
  clicks the Budget group card
- **THEN** a group titled "Park improvements" with a budget exists at the end of the section and
  the dialog becomes that group's

#### Scenario: Budget group card is greyed out without a map

- **WHEN** the New question dialog opens on a form section
- **THEN** the Budget group card is shown disabled with the same reason as the map questions

#### Scenario: No price block outside a budget group

- **WHEN** the creator opens a point question that is not in a budget group
- **THEN** no Price block is shown
