## ADDED Requirements

### Requirement: Budget questions round-trip

The structure export SHALL write a budget question's `validation_settings['budget']` and its
items' `description`, `cost` and `max_count` keys (under the question's `budget` key, since
`validation_settings` is not exported), and the layer binding of a `source == 'layer'` question
by its position in the exported `layers` array, like Objects on the map; import SHALL pass the settings through `normalise_budget_settings` and
the items through `normalise_choice_extras`, bind the layer when that layer was imported and otherwise fall back to `source == 'list'`
with a report line; an invalid record imports as the defaults with a report line. A group's `budget` and a geo question's `price` SHALL ride the archive the same way. Responses
import SHALL restore `Answer.allocation`.

#### Scenario: Settings survive

- **WHEN** a survey with a Split question (total 100, percent, step 5) is exported and imported
- **THEN** the imported question has the same settings

#### Scenario: Missing layer falls back

- **WHEN** an imported layer-sourced budget names a layer the archive does not contain
- **THEN** the question is imported with `source == 'list'` and the report says so
