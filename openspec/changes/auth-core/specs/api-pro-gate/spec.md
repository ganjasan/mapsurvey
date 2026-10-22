## ADDED Requirements

### Requirement: `api` is a Pro feature in the registry
`billing/features.py` SHALL define the feature `api` for `PLAN_PRO` only. No other column or flag SHALL decide API entitlement.

#### Scenario: Registry
- **WHEN** `features_for_plan(PLAN_PRO)` and `features_for_plan(PLAN_FREE)` are read
- **THEN** `api` is in the first and not in the second

### Requirement: Pro is checked at the resource, per request, on the owning organisation
`require_pro_api(principal, organization)` SHALL consult `billing.entitlements.for_organization(organization).has("api")` on every call and raise `403 {"error": "pro_required", "organization": <slug>, "upgrade_url": <billing page>}` otherwise. The organisation SHALL be the one that owns the object the request is about (`survey.organization`), never the token's user or binding. Token issuance and validation SHALL NOT depend on plan.

#### Scenario: Free workspace survey
- **WHEN** a token of a Pro workspace's owner is used on a survey owned by a Free workspace
- **THEN** the response is `403 pro_required` naming the Free workspace

#### Scenario: Free collaborator on a Pro survey
- **WHEN** a user whose own workspace is Free, but who is an editor collaborator on a Pro workspace's survey, uses their token on that survey
- **THEN** the call is allowed within the editor role

#### Scenario: Subscription lapses
- **WHEN** `current_period_end` passes between two calls with the same token
- **THEN** the first call succeeds, the second is `403 pro_required`, and the token row is unchanged

#### Scenario: Renewal
- **WHEN** the webhook extends `current_period_end` after a lapse
- **THEN** the same token succeeds again without re-minting

#### Scenario: Refund
- **WHEN** the subscription moves to a refunded/chargeback state
- **THEN** the next call is `403 pro_required`

### Requirement: Mixed-workspace listings
`gates.pro_organizations(principal)` SHALL return the principal's organisations holding `api` and the count of those that do not, so a list endpoint can return `hidden_by_plan`. Minting a personal token SHALL be allowed on Free with a note on the page; `/api/v1/me` SHALL be allowed on Free.

#### Scenario: One Pro, two Free
- **WHEN** a member of one Pro and two Free workspaces calls `pro_organizations()`
- **THEN** the Pro workspace is returned and `hidden_by_plan == 2`
