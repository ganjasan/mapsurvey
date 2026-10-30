## ADDED Requirements

### Requirement: A published survey outside its period is not answerable
`check_survey_access` SHALL apply the canonical survey's period (capability `survey-schedule`)
to a `published` survey after the held-for-review check and before the password gate. Before
`opens_at` it SHALL render the "opens on" page with status `200` and `noindex`; at or after
`closes_at` it SHALL render the closed page a `closed` survey gets. Neither page SHALL create a
`SurveySession`. Signed-in users with the `editor` role or above SHALL bypass the period as they
bypass every other rule. `draft`, `testing`, `closed` and `archived` surveys SHALL respond exactly
as before.

#### Scenario: Not yet open
- **GIVEN** a published survey whose `opens_at` is in the future
- **WHEN** an anonymous visitor requests it
- **THEN** the status is `200`, the body names the survey and its opening time,
  `X-Robots-Tag` says `noindex`, and no session is created

#### Scenario: Already closed by the clock
- **GIVEN** a published survey whose `closes_at` is in the past and whose status is still `published`
- **WHEN** an anonymous visitor requests it
- **THEN** the response is the closed page

#### Scenario: Held wins over the period
- **GIVEN** a published survey held by content review with `opens_at` in the future
- **WHEN** an anonymous visitor requests it
- **THEN** the response is the `404` unavailable page

#### Scenario: Password gate after the period
- **GIVEN** a published, password-protected survey inside its period
- **WHEN** an anonymous visitor requests it
- **THEN** they are redirected to the password page as before
