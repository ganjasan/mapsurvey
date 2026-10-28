# api-access-rights Specification

## Purpose
The scopes registry and how a token's effective rights are scope ∩ organisation role ∩ survey role through the editor's own role helpers; lookups answer 404 (never 403) and always go through the survey; `/api/v1/me` explains the token.
## Requirements
### Requirement: Scopes registry
`api/scopes.py` SHALL define the ordered registry `surveys:read`, `surveys:write`, `surveys:publish`, `surveys:delete`, `responses:read`, `responses:moderate`, each with a human label, and SHALL be the one source for the token form, `OAUTH2_PROVIDER["SCOPES"]`, and every scope check. An unknown scope string SHALL be refused at the form and at `OAUTH2_PROVIDER` validation. `responses:moderate` SHALL NOT be among the scopes checked by default on the token form.

#### Scenario: Unknown scope on the form
- **WHEN** the create form posts scope `admin:all`
- **THEN** the form is invalid

#### Scenario: Moderation is opt-in on the token form
- **WHEN** the token form renders
- **THEN** `responses:moderate` is offered and unchecked

### Requirement: Scope is an upper bound checked before any object is loaded
`require_scope(principal, scope)` SHALL raise `403 scope_missing` naming the missing scope when the principal lacks it. `@api_endpoint(audience, scopes=(...))` SHALL call it for each listed scope before the view body runs.

#### Scenario: Read-only token on a write
- **WHEN** a token with only `surveys:read` calls an endpoint declared with `scopes=("surveys:write",)`
- **THEN** the response is `403 {"error": "scope_missing", "scope": "surveys:write"}` and no object was loaded

### Requirement: Effective rights are scope ∩ organisation role ∩ survey role
`survey_for(principal, uuid, min_role)` SHALL resolve the survey the way the editor does — `get_effective_survey_role(principal.user, survey)` — and SHALL raise `404 not_found` when the user has no role, a role below `min_role`, or the token is bound to an organisation other than the survey's. It SHALL never answer 403 for an existing survey, so a token cannot learn which surveys exist. `section_for(principal, survey, id)` and `question_for(principal, survey, id)` SHALL filter by the given survey and raise `404 not_found` otherwise.

#### Scenario: Survey of another workspace
- **WHEN** a token of a user who is not a member of survey S's organisation asks for S
- **THEN** the response is `404 not_found`, byte-identical to the response for a random uuid

#### Scenario: Viewer role on an editor action
- **WHEN** a viewer-role user's token with `surveys:write` calls `survey_for(..., min_role="editor")`
- **THEN** the result is `404 not_found`

#### Scenario: Workspace-bound token
- **WHEN** a token bound to organisation A asks for a survey of organisation B where the user is also a member
- **THEN** the result is `404 not_found`

#### Scenario: Section id under the wrong survey
- **WHEN** `section_for(principal, survey_A, id_of_section_in_B)` is called
- **THEN** the result is `404 not_found`

### Requirement: `/api/v1/me` explains the token
`GET /api/v1/me` SHALL require a valid token with audience `api` and no particular scope or plan, and SHALL answer `{"user": {"id", "username", "email"}, "workspaces": [{"id", "slug", "name", "role", "plan", "api": bool}], "token": {"kind", "scopes", "audiences", "organization", "expires", "label"}}`, where `workspaces` lists the user's memberships (only the bound one when the token is bound) and `api` is whether that workspace holds the `api` feature.

#### Scenario: Free and Pro workspaces
- **WHEN** a user who is a member of a Free and a Pro workspace calls `/me`
- **THEN** both workspaces are listed, with `api: false` and `api: true` respectively, and the call is `200` even though one is Free

#### Scenario: Bound token
- **WHEN** a token bound to workspace A calls `/me`
- **THEN** only workspace A is listed and `token.organization` names it

