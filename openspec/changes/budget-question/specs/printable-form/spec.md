## ADDED Requirements

### Requirement: Paper shapes for budgets

`QUESTION_SHAPES` SHALL print a Split `budget` as a table of items with a blank amount cell
carrying the symbol and a Total row stating the budget, and a Projects `budget` as a checkbox per
item with its cost and a Total row. A budget group SHALL print a note under its heading stating
the budget and that the marks in the group must not cost more together; a priced geo question's
note SHALL name its price ("Price: £2 000 each"). The fixed strings SHALL come from the
respondent catalogs.

#### Scenario: Split prints a table

- **WHEN** a form with a Split question is printed
- **THEN** the page shows one row per item with an amount cell and "Total: £20M"

#### Scenario: A priced mark says its price

- **WHEN** a form with a budget group holding a £2 000 bench question is printed
- **THEN** the group heading is followed by the budget note and the bench question's note names "£2 000 each"
