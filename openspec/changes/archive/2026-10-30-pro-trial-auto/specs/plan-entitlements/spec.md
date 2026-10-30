## ADDED Requirements

### Requirement: Pro controls carry one mark from the registry
A template tag `{% pro_badge org "key" %}` SHALL render the one Pro mark next to a control gated on a registry feature, in exactly one of four states computed from `for_organization` and `billing.trial`: `plan` (the plan includes the feature) → a quiet "Pro"; `trial` (a live trial has a remainder for it) → "Pro trial · N left", or "Pro trial · until <date>" for an uncapped allowance; `startable` (the workspace is startable for it) → "Pro · free to try", with a tooltip saying the first use starts the workspace's free trial; `locked` (anything else) → a lock and "Pro" linking to the workspace's Plan & billing. An unknown key SHALL raise in tests (`TEMPLATE_DEBUG`) and render nothing in production. The badge switch in survey settings, *Enter a response* on Responses, the API & connections page and the Pro help entry points (help menu, account menu) SHALL use it; no template SHALL hand-write a Pro label next to a gated control.

#### Scenario: Four states
- **WHEN** the tag is rendered for `api` on a Pro workspace, on a Free one with a live trial at 20 of 500, on a startable Free one, and on a Free one whose owner used their trial elsewhere
- **THEN** it renders "Pro", "Pro trial · 480 left", "Pro · free to try" and a locked "Pro" linking to Plan & billing respectively

#### Scenario: Uncapped feature in a trial
- **WHEN** the tag is rendered for `operator_entry` on a Free workspace with a live trial ending 28 January
- **THEN** it renders "Pro trial · until 28 Jan"

#### Scenario: No hand-written marks
- **WHEN** the editor templates are searched for a Pro label next to a gated control outside the tag's own template
- **THEN** none is found

## MODIFIED Requirements

### Requirement: Views and templates gate on features through shared helpers
A view decorator `require_feature(key)` SHALL return HTTP 403 with an upgrade hint — and the
viewer's trial state — for authenticated members of an organisation for which
`billing.trial.may(org, key)` is false (neither the plan, nor a live trial's remainder, nor a
startable trial admits a new use), and a template tag `{% has_feature org "key" as var %}` SHALL
expose `covers(key)` (the feature is in force by plan or by a live trial, spent or not) to
templates, which render states set earlier. Controls that OFFER a new use SHALL be decided by
`billing.trial.may`. The decorator SHALL NOT count or start anything; the view counts through
`billing.trial.use` at the point the feature is used.

#### Scenario: Decorator blocks a Free organisation
- **WHEN** a member of a Free organisation that is not startable (its owner used their trial elsewhere) requests a view decorated with `require_feature("pro_help")`
- **THEN** the response is HTTP 403 and its body links to the billing page

#### Scenario: Decorator admits a startable organisation without starting it
- **WHEN** a member of a startable Free organisation GETs the same view
- **THEN** the view runs and no grant exists

#### Scenario: Decorator admits a live trial
- **WHEN** a member of a Free organisation whose trial has a `pro_help` remainder requests the same view
- **THEN** the view runs

#### Scenario: Template tag on a Pro organisation
- **WHEN** a template evaluates `has_feature` for a Pro organisation and `unbranded`
- **THEN** the variable is true

#### Scenario: Template tag on a spent trial
- **WHEN** a template evaluates `has_feature` for a Free organisation whose live trial's `unbranded` allowance is spent
- **THEN** the variable is true, while `may("unbranded")` is false

#### Scenario: Template tag after the trial
- **WHEN** the same trial has expired
- **THEN** the variable is false
