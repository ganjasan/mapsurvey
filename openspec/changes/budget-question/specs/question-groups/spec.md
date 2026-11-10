## ADDED Requirements

### Requirement: A group may carry a budget over its map questions

A question group SHALL accept a budget — `QuestionGroup.budget = {"total", "unit", "symbol"}`
through `budget.normalise_budget_settings(…, 'group')`, null for an ordinary group — set in the
group dialog's Budget block (total, unit, symbol; empty total = none) and through the API. A
budget group SHALL render its bar in its header on every respondent surface, show a "£60k"
badge in the editor list, open as "Budget group" with its own tips (prices per mark / metre /
m², what respondents see, unpriced questions are free, results) instead of the display-style
tips, and warn in its dialog when some of its map questions have no price. It SHALL also be
creatable from the "New question" picker's Budget group card (spec question-type-picker).
Its total and unit SHALL be structure on a live survey; its symbol and title content. The
budget SHALL travel with the ZIP (`budget` key), every copy and the draft copy. Groups in a
pop-up SHALL NOT carry a budget (their members cannot be map questions).

#### Scenario: Setting a total makes the group a budget

- **WHEN** a creator types 60000 and £ in the group's Budget block
- **THEN** the group's badge reads "£60k" and its respondent header shows the bar

#### Scenario: Clearing the total removes it

- **WHEN** the creator empties the total
- **THEN** the group is an ordinary group again and its questions place marks without a cap

#### Scenario: The budget survives the archive and the draft copy

- **WHEN** a survey with a budget group is exported and imported, or edited in unpublished changes
- **THEN** the group keeps its total, unit and symbol
