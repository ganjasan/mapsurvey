# plan-entitlements Specification

## Purpose
TBD - created by archiving change paywall-payproglobal. Update Purpose after archive.
## Requirements
### Requirement: Entitlements come from one function over stored subscriptions
`billing.entitlements.for_organization(org)` SHALL return the organisation's plan (`free` or
`pro`), state, `until`, the set of features its plan enables, and — from the second entitlement
source — the live trial grant (`trial`) and its `allowances`, computed solely from the
organisation's current `Subscription` row, its `EntitlementGrant` rows and the feature registry.
`has(key)` SHALL answer from the plan alone; `may(key)` SHALL answer from the plan or a live
allowance with a remainder. No PayPro API or network call SHALL occur.

#### Scenario: Organisation without subscription
- **WHEN** an organisation has no `Subscription` and no grant
- **THEN** plan is `free`, state `none`, `until` is `None`, features is empty, `trial` is `None` and `may(key)` is false for every key

#### Scenario: Active Pro
- **WHEN** the current subscription is `active` with `current_period_end` in the future
- **THEN** plan is `pro`, state `active`, features contains `unbranded`, `pro_help` and `api`

#### Scenario: Free with a live trial
- **WHEN** an organisation has no subscription and a live trial grant with a remainder for `api`
- **THEN** plan is `free`, `has('api')` is false and `may('api')` is true

### Requirement: Access survives suspension and termination until the paid period ends
The organisation SHALL be Pro while `now < current_period_end` in states `active`, `past_due`,
`suspended` and `terminated`, and SHALL NOT be Pro in states `finished`, `refunded`,
`charged_back`, or once `current_period_end` has passed in any state.

#### Scenario: Cancelled but paid up
- **WHEN** status is `terminated` and `current_period_end` is 10 days ahead
- **THEN** plan is `pro` with state `cancelling` and `until` equal to the period end

#### Scenario: Period elapsed
- **WHEN** status is `suspended` and `current_period_end` was yesterday
- **THEN** plan is `free` with state `lapsed`

#### Scenario: Refunded
- **WHEN** status is `refunded` even with a future `current_period_end` stored earlier
- **THEN** plan is `free`

### Requirement: Features are declared in a registry, not in columns
Pro capabilities SHALL be declared in `billing/features.py` as named entries mapping a feature
key to the plans that include it and a human label. Adding a feature SHALL require only a new
registry entry. The registry SHALL contain `unbranded`, `pro_help`, `api` and `operator_entry`,
all for plan `pro`.

#### Scenario: Registry drives the feature set
- **WHEN** a new key `custom_domain` is added to the registry for plan `pro`
- **THEN** `for_organization(pro_org).features` contains `custom_domain` without any migration or model change

#### Scenario: Operator entry is a Pro feature
- **WHEN** entitlements are computed for a Pro organisation and for a Free one
- **THEN** `operator_entry` is in the Pro organisation's features and absent from the Free one's

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

### Requirement: The AI quota seam reads entitlements
`survey.ai.quota.check_quota(organization, kind)` SHALL obtain `for_organization(organization)`
and SHALL return without raising for every plan in this change; it SHALL be the only place a
future generation limit is enforced.

#### Scenario: Free organisation generates
- **WHEN** `check_quota` is called for a Free organisation
- **THEN** it returns `None` and the entitlement lookup was performed

### Requirement: Lapsing is observed once
A nightly task SHALL find subscriptions whose entitlement turned `free` since the previous run,
emit `plan_lapsed` once per subscription, and send one "your Pro plan has ended" email to the
organisation's owners. Running the task twice SHALL NOT repeat either.

#### Scenario: Lapse detected
- **WHEN** the task runs the day after a suspended subscription's period end
- **THEN** `plan_lapsed` is emitted, one email per owner is sent, and `lapse_notified_at` is set

#### Scenario: Idempotent rerun
- **WHEN** the task runs again
- **THEN** nothing is emitted or sent for that subscription

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

