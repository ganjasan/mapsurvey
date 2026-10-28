## MODIFIED Requirements

### Requirement: Pro is checked at the resource, per request, on the owning organisation
`require_pro_api(principal, organization)` SHALL consult `billing.entitlements.for_organization(organization)` on every call: when the plan includes `api` (`has("api")`) the call proceeds and nothing is counted; otherwise it SHALL consume one call from the organisation's live trial allowance for `api` (`billing.trial.consume`) and proceed when a call was available, else raise `403 {"error": "pro_required", "organization": <slug>, "upgrade_url": <billing page>, "trial": "exhausted" | "expired" | "none"}`. The organisation SHALL be the one that owns the object the request is about (`survey.organization`), never the token's user or binding. Token issuance and validation SHALL NOT depend on plan. MCP tool calls reach this gate through `api.v1.deps` and are counted the same way.

#### Scenario: Free workspace survey
- **WHEN** a token of a Pro workspace's owner is used on a survey owned by a Free workspace without a trial
- **THEN** the response is `403 pro_required` naming the Free workspace with `trial: "none"`

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

#### Scenario: Trial call counted
- **WHEN** a token is used on a survey of a Free workspace whose live trial has 2 `api` calls left
- **THEN** the call succeeds and the allowance reads 1 left; the next succeeds and reads 0; the third is `403 pro_required` with `trial: "exhausted"`

#### Scenario: MCP tool call counted
- **WHEN** an MCP client calls `get_survey` on a survey of that workspace
- **THEN** the allowance decreases by one exactly as for a REST request

#### Scenario: Pro workspace never consumes
- **WHEN** a workspace is Pro and also holds a live trial and a token is used on its survey
- **THEN** the call succeeds and the allowance is unchanged
