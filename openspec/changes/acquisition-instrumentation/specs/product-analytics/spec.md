## MODIFIED Requirements

### Requirement: The trust page describes tracking accurately

`/trust/` SHALL NOT claim site-wide absence of cookies or third-party trackers while product
analytics runs on creator-facing pages. The claims SHALL be scoped to the audience they were written
about — survey respondents — and the page SHALL state that creator-facing pages carry product
analytics (PostHog) and a first-party attribution cookie. It SHALL state that respondent-facing
pages (surveys, thanks pages, public results) load no third-party analytics script of any kind and
SHALL NOT name Plausible.

#### Scenario: Cookie and tracker claims are scoped to respondents
- **WHEN** a visitor reads the Data Privacy section of `/trust/`
- **THEN** the no-cookies and no-third-party-tracker claims are stated as applying to survey
  respondents
- **AND** the page discloses that creator-facing pages use product analytics and a first-party
  attribution cookie

#### Scenario: Respondent pages carry no third-party analytics
- **GIVEN** `POSTHOG_PROJECT_KEY` is configured
- **WHEN** a respondent loads any page in the survey-taking flow, the thanks page or a public
  results page
- **THEN** the page contains no third-party analytics script and no analytics event is fired

#### Scenario: Plausible is not mentioned
- **WHEN** the trust page and the generated DPA are rendered
- **THEN** neither names Plausible or claims aggregate analytics on survey pages
