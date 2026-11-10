## ADDED Requirements

### Requirement: The `budget_map` feature

The features registry SHALL declare `budget_map` ("Budget questions over a reference layer":
a `budget` question whose items are a layer's objects) as a Pro feature with a trial allowance
entry. The gate SHALL ask `billing.trial.may(org, 'budget_map')` and count through
`billing.trial.use` once per question that gains the layer source; budget groups and typed-list
budgets are not gated; nothing is checked on respondent surfaces.

#### Scenario: Free plan lacks it

- **WHEN** `features_for_plan('free')` is read
- **THEN** `budget_map` is not in it

#### Scenario: Trial start on first use

- **WHEN** an owner of a workspace that never had a trial switches a budget question's items to a layer
- **THEN** the trial starts with `trigger == 'budget_map'` and the use is counted
