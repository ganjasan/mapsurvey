## MODIFIED Requirements

### Requirement: The form is a Pro feature; Free organisations see the offer
`/org/<slug>/help/` SHALL render the request form for members of organisations for which
`may("pro_help")` is true (the plan includes it, or a live trial has a `pro_help` remainder). For
members of other organisations it SHALL render the service description with, for the owner, the
"Try Pro" control when the trial state is `available` (posting to the claim endpoint with `next`
set to the help page) or an Upgrade link otherwise, and for other members a "ask your
organisation owner" note; when the trial's `pro_help` allowance is used up or the trial has
expired the page SHALL say so in one sentence. It SHALL reject POSTs from organisations for which
`may("pro_help")` is false with HTTP 403. A stored request from an organisation whose plan lacks
`pro_help` SHALL consume one `pro_help` allowance before it is saved; if none is left nothing is
stored and the Free view renders.

#### Scenario: Pro member opens the page
- **WHEN** an editor of a Pro organisation opens `/org/<slug>/help/`
- **THEN** the request form is rendered

#### Scenario: Free owner opens the page
- **WHEN** the owner of a Free organisation without a trial opens the page
- **THEN** the service description and the "Try Pro" control are rendered and no form

#### Scenario: Free POST
- **WHEN** a member of a Free organisation without a trial POSTs to the page
- **THEN** the response is HTTP 403 and nothing is stored

#### Scenario: Trial member submits
- **WHEN** an editor of a Free organisation whose trial has 1 `pro_help` left submits a valid request
- **THEN** a `ProHelpRequest` row exists, the allowance reads 0 left, and the page then renders the service description with the "trial used" sentence instead of the form
