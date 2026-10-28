## MODIFIED Requirements

### Requirement: Scopes registry
`api/scopes.py` SHALL define the ordered registry `surveys:read`, `surveys:write`, `surveys:publish`, `surveys:delete`, `responses:read`, `responses:moderate`, each with a human label, and SHALL be the one source for the token form, `OAUTH2_PROVIDER["SCOPES"]`, and every scope check. An unknown scope string SHALL be refused at the form and at `OAUTH2_PROVIDER` validation. `responses:moderate` SHALL NOT be among the scopes checked by default on the token form.

#### Scenario: Unknown scope on the form
- **WHEN** the create form posts scope `admin:all`
- **THEN** the form is invalid

#### Scenario: Moderation is opt-in on the token form
- **WHEN** the token form renders
- **THEN** `responses:moderate` is offered and unchecked
