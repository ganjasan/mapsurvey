## ADDED Requirements

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
