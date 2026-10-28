## MODIFIED Requirements

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

### Requirement: Views and templates gate on features through shared helpers
A view decorator `require_feature(key)` SHALL return HTTP 403 with an upgrade hint — and the
viewer's trial state — for authenticated members of an organisation for which `may(key)` is
false, and a template tag `{% has_feature org "key" as var %}` SHALL expose `covers(key)` (the
feature is in force by plan or by a live trial, spent or not) to templates, which render states
set earlier. Both SHALL consult `for_organization` and nothing else.

#### Scenario: Decorator blocks a Free organisation
- **WHEN** a member of a Free organisation without a trial requests a view decorated with `require_feature("pro_help")`
- **THEN** the response is HTTP 403 and its body links to the billing page

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
