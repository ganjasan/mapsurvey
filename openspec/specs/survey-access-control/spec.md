# survey-access-control Specification

## Purpose
TBD - created by archiving change tenant-data-exposure. Update Purpose after archive.
## Requirements
### Requirement: No public surface enumerates surveys
The platform SHALL NOT expose any unauthenticated route that lists surveys belonging to
more than one organization. Survey discovery for anonymous visitors SHALL be limited to
the landing page, which lists only surveys with `visibility` in (`public`, `demo`) that are
canonical and not in `draft` status.

The route `/surveys/` SHALL NOT render a survey list. It SHALL respond with a permanent
redirect to `/`.

#### Scenario: The former listing route redirects
- **WHEN** any visitor requests `/surveys/`
- **THEN** the response SHALL be `301` with `Location: /`
- **AND** the response body SHALL NOT contain any survey name or survey UUID

#### Scenario: A private survey is not discoverable anonymously
- **GIVEN** a survey with `visibility='private'`
- **WHEN** an anonymous visitor requests `/` and `/surveys/`
- **THEN** neither response SHALL contain that survey's name or UUID

#### Scenario: A draft survey is not discoverable anonymously
- **GIVEN** a survey with `visibility='public'` and `status='draft'`
- **WHEN** an anonymous visitor requests `/`
- **THEN** the response SHALL NOT contain that survey's name or UUID

#### Scenario: The sitemap does not advertise the removed route
- **WHEN** `/sitemap.xml` is fetched
- **THEN** it SHALL NOT contain a `<loc>` entry ending in `/surveys/`
- **AND** it SHALL still contain `<loc>` entries of the form `/surveys/<uuid>/`

### Requirement: Exporting responses requires a role on the survey
The response export at `/surveys/<survey_slug>/download` SHALL require the requesting user
to hold an effective survey role of at least `viewer` on the survey named by the URL, as
computed by `get_effective_survey_role`. Authentication alone SHALL NOT be sufficient.

The role SHALL be evaluated once, against the survey the URL resolves to, before any
version expansion. When `?version=` selects a family of archived versions, a role on the
resolved survey SHALL grant the whole family.

#### Scenario: A user with a role exports successfully
- **GIVEN** a signed-in user whose effective survey role is `viewer` or higher
- **WHEN** they request `/surveys/<uuid>/download`
- **THEN** the response SHALL be `200` with the ZIP export

#### Scenario: A signed-in user from another organization is denied
- **GIVEN** a signed-in user who is not a member of the survey's organization and holds no
  `SurveyCollaborator` row for it
- **WHEN** they request `/surveys/<uuid>/download`
- **THEN** the response SHALL be `404`
- **AND** no part of the export SHALL be written to the response

#### Scenario: An anonymous visitor is denied
- **GIVEN** an anonymous visitor
- **WHEN** they request `/surveys/<uuid>/download`
- **THEN** the response SHALL NOT be `200`
- **AND** the response SHALL NOT contain export data

#### Scenario: A collaborator on the canonical survey may export all versions
- **GIVEN** a user with organization role `editor`, which confers no baseline survey role,
  whose access comes from a `SurveyCollaborator` row on the canonical survey and who has no
  such row on its archived version headers
- **WHEN** they request `/surveys/<uuid>/download?version=all`
- **THEN** the response SHALL be `200` and SHALL include data for the archived versions

#### Scenario: Denial does not disclose existence
- **GIVEN** a signed-in user with no role on any survey in the target organization
- **WHEN** they request `/surveys/<uuid>/download` for a survey that exists, and
  `/surveys/<random-uuid>/download` for one that does not
- **THEN** both responses SHALL have status `404`
- **AND** the two responses SHALL be indistinguishable to the caller

### Requirement: Visibility governs discovery, not access
`SurveyHeader.visibility` SHALL determine only whether a survey is listed on public
surfaces. It SHALL NOT be consulted when deciding whether a visitor holding the survey's
URL may open it. A `published` survey without a password SHALL remain openable by any
visitor holding its link regardless of `visibility`.

#### Scenario: A private published survey opens by link
- **GIVEN** a survey with `visibility='private'`, `status='published'`, and no password
- **WHEN** an anonymous visitor requests `/surveys/<uuid>/`
- **THEN** the visitor SHALL be admitted to the survey

#### Scenario: A public draft survey stays closed
- **GIVEN** a survey with `visibility='public'` and `status='draft'`
- **WHEN** an anonymous visitor requests `/surveys/<uuid>/`
- **THEN** the response SHALL be `404`

### Requirement: A survey that cannot be opened returns an explanation, not a blank 404
A `draft` survey denied by `check_survey_access` SHALL respond with HTTP status `404` and
SHALL render an "unavailable" page rather than Django's default 404 body.

The page SHALL NOT name the survey and SHALL NOT state which condition applied. Responses for
a `draft` survey, a deleted survey, and a UUID that names no survey SHALL be identical in
status, headers and body, except for occurrences of the requested path itself, which the
navbar's login link echoes back and which the visitor supplied. A visitor SHALL NOT be able to
learn from the response whether the UUID names a real survey.

The status code SHALL remain `404`. An explanatory page served as `200` would keep the URL
eligible for indexing, which is the defect this requirement exists to close.

#### Scenario: A draft survey returns an explanation with a 404 status
- **GIVEN** a survey with `status='draft'`
- **WHEN** an anonymous visitor requests `/surveys/<uuid>/`
- **THEN** the status code SHALL be `404`
- **AND** the body SHALL contain the unavailable-page text
- **AND** the body SHALL NOT contain the survey's name

#### Scenario: A draft and an unknown UUID are indistinguishable
- **GIVEN** a survey with `status='draft'`
- **WHEN** an anonymous visitor requests that survey's URL and a URL with a random UUID
- **THEN** both responses SHALL have status `404`
- **AND** their bodies SHALL be identical once each response's own requested UUID is
  substituted for a placeholder
- **AND** both SHALL carry the same `X-Robots-Tag`

#### Scenario: Access decisions are otherwise unchanged
- **GIVEN** surveys in `published`, `testing`, `closed` and `archived` status
- **WHEN** an anonymous visitor requests each survey's URL
- **THEN** each SHALL respond exactly as it did before this change

