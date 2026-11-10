## ADDED Requirements

### Requirement: The budget question is one input type; the map side is a group setting

The system SHALL provide the input type `budget` with a `mode` of `split` or `projects`, labelled
"Budget" in the picker, a member of `CHOICE_TYPES` and NOT of `GEO_TYPES`. Budgets on the map
SHALL NOT be a question type: they are a setting of a question group (see "A budget group bounds
the marks of its priced map questions"), so the geo types stay the four the map knows and keep
every behaviour they have.

#### Scenario: budget is not a geo type and no geo type was added

- **WHEN** the type registry is read
- **THEN** `'budget' not in GEO_TYPES` and `GEO_TYPES` is `point, line, polygon, spraycan`

#### Scenario: budget sits in any section

- **WHEN** a section has layout `form` or `image`
- **THEN** a `budget` question may be added to it

### Requirement: Budget settings are one validated record

Budget settings SHALL live in `validation_settings['budget']` (a `budget` question) or
`QuestionGroup.budget` (a budget group) with the keys `mode`, `total`, `unit`
(`currency` | `points` | `percent`), `symbol` (≤ 4 characters), `step`, `rule` (`all` | `upto`),
`min_items`, `show_shares`, `source` (`list` | `layer`) and `cost_property`; a group's record
holds `total`, `unit` and `symbol` only. `budget.normalise_budget_settings()` SHALL be the only
validator and SHALL be applied by the question form, the group form, the ZIP import and the API
alike. `total` and `step` MUST be positive numbers with `step ≤ total`; `unit == 'percent'` SHALL
force `total = 100` and an empty `symbol`; `rule` applies to `split` only.

#### Scenario: Invalid settings are refused with a field error

- **WHEN** a creator saves a `budget` question with `step` greater than `total`
- **THEN** the save is refused and the error names the step field

#### Scenario: Percent fixes the total

- **WHEN** a creator picks the unit `percent` and types a total of 50
- **THEN** the stored total is 100 and the symbol is empty

#### Scenario: A group's record has no step and no mode

- **WHEN** a group budget record with a step is normalised
- **THEN** it holds `total`, `unit` and `symbol` only

### Requirement: Items carry description and cost as choice extras

An item of a `budget` question SHALL be a `choices` entry whose optional keys `description`
(plain text, ≤ 300 characters) and `cost` (number ≥ 0) are trimmed, capped and dropped-if-invalid
by `normalise_choice_extras` on every save path and on import. For `mode == 'projects'` every
item MUST have a `cost`; the save SHALL be refused otherwise, naming the item. Every other
consumer of `choices` SHALL ignore these keys.

#### Scenario: A project without a cost is refused

- **WHEN** a creator saves a Projects budget whose third item has no cost
- **THEN** the save is refused and the error names the third item

#### Scenario: Extras are capped, not rejected

- **WHEN** an imported item has a 500-character description
- **THEN** the stored description is 300 characters and the import reports nothing

### Requirement: Items may come from a reference layer

A `budget` question with `source == 'layer'` SHALL take its items from the objects of
`Question.layer` — key = object key, name = object title, description = object description,
cost = the object's property named by `cost_property` coerced to a number. It SHALL place the
layer on the section's map the way `layer_objects` does (`layers.section_layer_ids`), and an
object with no numeric cost SHALL be listed as not selectable with a reason. Picking happens in
the panel list; an "Add to my budget" action in the object's map popup is a follow-up. The bound
layer SHALL NOT be deletable while the question exists. Two questions on one section SHALL NOT
bind the same layer.

#### Scenario: Costs are read from the property

- **WHEN** a layer object has `cost_gbp: "2500000"` and the question's `cost_property` is `cost_gbp`
- **THEN** the item costs 2 500 000

#### Scenario: Object without a cost

- **WHEN** a layer object has no value under `cost_property`
- **THEN** the object is shown on the map and in the list, cannot be picked, and the editor
  counts it in a "N objects have no cost" notice

### Requirement: The respondent always sees the remainder

Every budget — a `budget` question and a budget group — SHALL render a budget bar with the
amount spent, the total and the remainder, updated on every change, formatted by one function
(`format_amount`: 20 000 000 with symbol £ → "£20M"). The bar SHALL be stacked, one segment per
item in the item's colour (a `budget` item's `color` extra; a group member's `Question.color`),
so the respondent sees what went where; an item without a colour takes the next colour of a fixed
palette. The Responses and public-results rows of an item SHALL use the same colour. A control
that would exceed the remainder SHALL be unavailable with the reason, never silently clamped
afterwards.

#### Scenario: The bar shows what went where

- **WHEN** a Split respondent gives Parks (green) £2M and Safety (blue) £1.5M of £20M
- **THEN** the bar holds a green 10 % segment followed by a blue 7.5 % segment

#### Scenario: Remainder updates live

- **WHEN** a Split respondent raises one item by one step
- **THEN** the bar shows the new spent amount and the remainder reduced by one step

#### Scenario: Unaffordable project

- **WHEN** a Projects respondent has £3M left and an unpicked project costs £4M
- **THEN** that project's control is disabled and its card says it is £1M over what is left

### Requirement: Split — amounts in the creator's step that add up to the budget

In `split` mode the respondent SHALL set each item's amount with steppers (±step) and, at
≥ 769 px, a slider; on a phone the amount SHALL be editable by typing (`inputmode=numeric`) and
rounded to the nearest step. Under `rule == 'all'` the section SHALL NOT submit until the
remainder is zero, and the Next button SHALL say how much is unallocated; under `rule == 'upto'`
a required question needs at least one non-zero item. A "spread the rest evenly" action SHALL
exist. The section POST has no error-render path (as for every other type: the client blocks
Next and says why), so the server SHALL recompute the sum and store NOTHING for a submission whose
amounts are not multiples of the step, exceed the total, or (under `all`) do not reach it —
the way an invalid ranking is stored as nothing.

#### Scenario: Must allocate all

- **WHEN** a respondent presses Next on a `split`/`all` question with £5.5M unallocated
- **THEN** Next is blocked and the block says "Allocate the whole £20M — £5.5M is still unallocated."

#### Scenario: Tampered short allocation stores nothing

- **WHEN** a crafted POST allocates 15.5M of a 20M `all` budget
- **THEN** no answer is stored and the section submits without an error

#### Scenario: Stored shape

- **WHEN** a respondent allocates 6M, 4M, 2.5M, 2M, 5.5M of a 20M budget
- **THEN** one `Answer` row holds `allocation = {"total": 20000000, "items": {"1": 6000000, …}}`
  and `selected_choices` is null

#### Scenario: Round-trip

- **WHEN** the respondent returns to the section
- **THEN** every stepper shows the stored amount

### Requirement: Projects — a set of items whose costs fit the budget

In `projects` mode the respondent SHALL tick items; the client SHALL block Next below
`min_items` (or one item when required). The server SHALL store nothing for a submission whose
picked costs exceed the total or that picks an item without a cost, and SHALL ignore unknown
items. There is no "spend it all" rule in this mode.

#### Scenario: Stored shape

- **WHEN** a respondent picks items 1, 3 and 4 costing 8M, 2.5M and 5M
- **THEN** `allocation = {"total": 20000000, "items": {"1": 8000000, "3": 2500000, "4": 5000000}}`

#### Scenario: Over budget is refused server-side

- **WHEN** a crafted POST picks items costing 21.5M of a 20M budget
- **THEN** no answer is stored

### Requirement: A map question may carry a price

A geo question (`point`, `line`, `polygon`, `spraycan`) SHALL accept a price in
`validation_settings['price'] = {"amount", "per"}`, validated by `budget.normalise_price()`:
`amount` > 0 and `per` one of `feature` (per mark), `length` (per metre, lines only) or `area`
(per square metre, polygons and spray clouds only); anything else is no price. The price is
offered in the question dialog only while the question sits in a budget group, and SHALL render
on the respondent's draw button as a caption (`format_price`: "£2k each", "£50 / m", "£30 / m²")
with `data-price-amount` / `data-price-per` for the page script. A question without a price under
a budget group places marks for free. The cost of a stored mark SHALL be `budget.feature_cost`:
the amount times 1, the metres of the line or the square metres of the area, measured in Web
Mercator corrected by cos(lat) / cos²(lat) like `spray.cloud_area_m2`.

#### Scenario: A price is per what the type can measure

- **WHEN** a point is priced per metre
- **THEN** the price is dropped; a line per metre and an area per square metre are kept

#### Scenario: Measures follow the server's projection

- **WHEN** a 1 km east–west line at 53.6°N is measured per metre
- **THEN** the measure is about 1000 m

### Requirement: A budget group bounds the marks of its priced map questions

A question group with `budget` set SHALL render its bar above its questions and SHALL let the
page sum the cost of the marks placed on its member geo questions. A draw button whose next
mark (priced per mark) would cost more than what is left SHALL be disabled with the reason; a
drawn line or area whose cost exceeds the remainder SHALL NOT be kept and the group's bar SHALL
say what it would have cost. While a priced mark is being placed — crosshair, tap-to-place or a
Leaflet.draw handler — a chip over the draw bar SHALL show the question, the running size and
cost of the shape (metres or m², following the pointer) and what would be left after it, since
the panel and its bar are hidden then. Editing a mark SHALL recompute the spend. The server SHALL admit the
stored marks of the group's members in stored order until the budget is spent and drop the rest —
a clamp like `max_features`, because the widget never posts them. Member questions without a
price and ordinary groups SHALL be unaffected. The geo questions keep every behaviour they have:
sub-questions, min/max features, tap-to-place, restore, export, paper.

#### Scenario: Marks are admitted in stored order until the budget is spent

- **WHEN** a £10k group holds benches at £2k each and paths at £5 a metre, and a POST places four
  benches and a 1 km path
- **THEN** the four benches (£8k) are stored and the path (£5k) is dropped

#### Scenario: A short path fits

- **WHEN** the same group receives one bench and a 200 m path
- **THEN** both are stored

#### Scenario: The next lamp does not fit

- **WHEN** a respondent has £3k left and lamps cost £5k each
- **THEN** the lamps' draw button is disabled and reads "£2 000 over what is left."

#### Scenario: The cost follows the pen

- **WHEN** a respondent with £55k left draws a 531 m path priced £50 a metre
- **THEN** the chip over the draw bar reads "New paths · 531 m · £26.55k · £28.45k left after it" and
  updates as the pointer moves

#### Scenario: A free question in the group

- **WHEN** a member question has no price
- **THEN** its marks are stored whatever the budget says

### Requirement: One aggregate for every read surface

`survey/budget_stats.py` SHALL compute, over clean sessions of the canonical survey and its
versions: for `split` per item `mean_share`, `mean_amount`, `median_amount`, `zero_share`, `n`;
for `projects` per item `pick_share`, `n` and `fits` (items by descending support while their
costs fit the total); for a budget group (`group_aggregate`) per priced member the number of
marks, the measure they add up to (count, metres or m²), their cost and the share of everything
spent, plus respondents and the mean spend. Shares SHALL be computed against the `total` stored
on each answer (Split/Projects). Responses, public results and export SHALL call it and compute
no aggregate of their own.

#### Scenario: Mean share uses the stored total

- **WHEN** 100 answers were given against a 20M total and 100 later ones against 25M
- **THEN** each answer's share is its amount over its own total before averaging

#### Scenario: The set that fits

- **WHEN** projects have support 71, 64, 58, 52, 40, 30 % and costs 8M, 2.5M, 1.5M, 5M, 3M, 1M
  under a 19M total
- **THEN** `fits` is the first four (17M) and the sixth (18M): the fifth does not fit, a cheaper
  one after it still may

#### Scenario: Group aggregate counts measures and spend

- **WHEN** two respondents placed three benches between them and one a 200 m path
- **THEN** benches read ×3 and £6k, the path 200 m and its cost, respondents 2

### Requirement: Responses shows the mode's aggregate

The Responses overview SHALL render a `budget` question's block with the respondent count, the
total and the per-item bars of its mode (Split: mean share and amount; Projects: pick share
with the fitting set marked), and a budget group's block — count or measure, cost and share of
spend per member — before the group's first member; the members' marks stay on the Map pane as
any geo answer.

#### Scenario: Group block before its members

- **WHEN** a survey has a budget group with two priced map questions and answers
- **THEN** the overview shows one block for the group with a row per member

### Requirement: Budget changes that invalidate answers are structural

The system SHALL treat changing a `budget` question's `mode`, `total`, `unit`, `step`, `source`
or `cost_property`, changing an item's `cost`, removing an item that has answers, changing a
budget group's `total` or `unit`, or changing a geo question's price as a structural edit on a
live survey (Unpublished changes); `rule`, `min_items`, `show_shares`, `symbol`, item names,
descriptions, icons, colours and a group's title SHALL be content edits.

#### Scenario: Total change goes to the draft

- **WHEN** a creator changes the total of a published Split question, or of a live budget group
- **THEN** the editor opens the Unpublished-changes gate instead of saving in place

#### Scenario: Renaming is live

- **WHEN** a creator renames an item of a published budget question, or a live budget group
- **THEN** the save applies in place

### Requirement: Budget groups are free; a budget over a layer is Pro

Budget groups and `budget` questions with a typed list SHALL be available on every plan. Only a
`budget` question with `source == 'layer'` SHALL require the feature `budget_map` on the owning
workspace, checked through `billing.trial.may` where the question is saved and counted through
`billing.trial.use` once per question that gains the source. Published surveys SHALL keep serving
respondents after a lapse. The layer-source switch SHALL carry `{% pro_badge org "budget_map" %}`;
the group dialog and the Budget group picker card SHALL NOT.

#### Scenario: Free workspace sets a group budget

- **WHEN** a creator of a Free workspace whose trial is used elsewhere sets a total on a group
- **THEN** the save applies and no trial is started

#### Scenario: Free workspace refused a layer budget

- **WHEN** the same creator switches a budget question's items to a layer's objects
- **THEN** the save is refused with the Pro-required answer of that surface

#### Scenario: Respondents unaffected by a lapse

- **WHEN** a workspace's Pro lapses after publishing a survey with a layer-sourced budget
- **THEN** respondents can still pick projects and submit

### Requirement: Budget questions speak the service dialect and the API

`QuestionForm` SHALL accept `vs_budget_<key>` fields for the settings record, `vs_price_amount`
/ `vs_price_per` for a geo question's price and the items' new keys in `choices_json`;
`QuestionGroupForm` SHALL accept `budget_total` / `budget_unit` / `budget_symbol` (an empty total
removes the budget). The REST `In` schemas (`budget`, `price` on questions; `budget` on groups)
and the MCP tools SHALL expose the same, with the references regenerated.

#### Scenario: API creates a Split question

- **WHEN** a client POSTs a `budget` question with `budget: {mode: "split", total: 100, unit: "percent", step: 5}` and five items
- **THEN** the question is created with those settings normalised

#### Scenario: API prices a line under a group budget

- **WHEN** a client PATCHes a group with `budget: {total: 60000, symbol: "£"}` and a line question
  with `price: {amount: 50, per: "length"}`
- **THEN** the group is a budget group and the line's marks cost £50 a metre

### Requirement: Strings are translated

Every new creator string SHALL be present in every offered creator catalog, and every respondent
string (the bar, the reasons, the price captions, the Next hint) in every respondent catalog;
item descriptions SHALL translate through the occurrence key
`question:<code>:choice:<code>:description`.

#### Scenario: Description row in the translation table

- **WHEN** a budget item has a description
- **THEN** the Translations tab shows a row for it keyed by the item's code
