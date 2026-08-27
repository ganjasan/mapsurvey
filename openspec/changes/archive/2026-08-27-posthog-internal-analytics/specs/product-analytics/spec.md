## ADDED Requirements

### Requirement: PostHog snippet is configuration-gated

The system SHALL render the PostHog tracking snippet only when `POSTHOG_PROJECT_KEY` is a non-empty
string. Both `POSTHOG_PROJECT_KEY` and `POSTHOG_API_HOST` SHALL be read from the environment, and
`POSTHOG_PROJECT_KEY` SHALL default to empty so that local development, the test suite and any
deployment that has not been given a key emit no tracking at all.

`POSTHOG_API_HOST` SHALL default to `https://eu.i.posthog.com` (PostHog Cloud EU) and SHALL be
overridable, so a PR preview can be pointed at a separate project without a code change.

#### Scenario: Unconfigured key renders nothing
- **WHEN** `POSTHOG_PROJECT_KEY` is empty and a tracked page is requested
- **THEN** the response body contains no PostHog snippet and no reference to the PostHog asset host

#### Scenario: Configured key renders the snippet
- **WHEN** `POSTHOG_PROJECT_KEY` is set to a project key and a tracked page is requested
- **THEN** the response body contains the PostHog snippet carrying that key
- **AND** the snippet is initialised against the configured `POSTHOG_API_HOST`

#### Scenario: API host is overridable
- **WHEN** `POSTHOG_API_HOST` is set to a value other than the default
- **THEN** the rendered snippet initialises against that host

### Requirement: Respondent-facing pages are never tracked

The system SHALL NOT render the PostHog snippet on pages whose path begins with any prefix in
`POSTHOG_EXCLUDED_PREFIXES`, regardless of whether `POSTHOG_PROJECT_KEY` is configured. The list
SHALL cover respondent-facing survey pages (`/surveys/`) and public results pages (`/r/`), whose
visitors are the customer's audience rather than ours.

The exclusion SHALL be enforced where the template context is built, not by omitting the include
from individual templates, so that a template added later inherits the correct behaviour.

#### Scenario: Respondent survey page is not tracked
- **GIVEN** `POSTHOG_PROJECT_KEY` is configured
- **WHEN** a respondent requests a survey page under `/surveys/`
- **THEN** the response body contains no PostHog snippet

#### Scenario: Public results page is not tracked
- **GIVEN** `POSTHOG_PROJECT_KEY` is configured
- **WHEN** a visitor requests a public results page under `/r/`
- **THEN** the response body contains no PostHog snippet

#### Scenario: Marketing and editor pages are tracked
- **GIVEN** `POSTHOG_PROJECT_KEY` is configured
- **WHEN** the landing page, an account page or an editor page is requested
- **THEN** the response body contains the PostHog snippet

#### Scenario: Plausible is unaffected by the exclusion
- **GIVEN** both `PLAUSIBLE_SCRIPT_URL` and `POSTHOG_PROJECT_KEY` are configured
- **WHEN** a respondent survey page is requested
- **THEN** the Plausible script is still rendered
- **AND** the PostHog snippet is not

### Requirement: Signed-in creators are identified

When a tracked page is rendered for an authenticated user, the snippet SHALL identify that user to
PostHog using the user's primary key as the distinct id, and SHALL attach `email`, `username` and
`date_joined` as person properties.

For anonymous visitors the snippet SHALL NOT call identify, and person profiles SHALL be created for
identified users only.

#### Scenario: Authenticated creator is identified by user id
- **GIVEN** `POSTHOG_PROJECT_KEY` is configured
- **WHEN** an authenticated user requests a tracked page
- **THEN** the rendered snippet identifies the user by their primary key
- **AND** carries their email, username and registration date as person properties

#### Scenario: Anonymous visitor is not identified
- **GIVEN** `POSTHOG_PROJECT_KEY` is configured
- **WHEN** an anonymous visitor requests the landing page
- **THEN** the rendered snippet contains no identify call
- **AND** no email address appears in the response body

#### Scenario: Person properties are HTML-safe
- **WHEN** an authenticated user's username or email contains characters significant in HTML or
  JavaScript
- **THEN** the rendered snippet escapes them so the page's script block stays well-formed

### Requirement: Session recording stays off

The rendered snippet SHALL disable session recording. Enabling it requires a masking policy and a
reviewed privacy statement, neither of which exists yet.

#### Scenario: Recording disabled in the rendered config
- **WHEN** the snippet is rendered on any tracked page
- **THEN** its initialisation disables session recording

### Requirement: Creator-facing survey analytics stay in our database

PostHog SHALL NOT receive respondent events. The existing respondent analytics — `SurveyEvent`,
`TrackedLink`, `survey/events.py` and `PerformanceAnalyticsService` — measure our customers'
respondents on behalf of the customer and SHALL remain a database-backed product feature, unchanged
by this change.

No PostHog capture call SHALL be added to any respondent-facing view, and no respondent event SHALL
be forwarded to PostHog from the server.

#### Scenario: Respondent event emission is unchanged
- **WHEN** a respondent starts a session, views a section, submits a section or completes a survey
- **THEN** a `SurveyEvent` row is written exactly as before
- **AND** nothing is sent to PostHog

#### Scenario: Performance tab is unaffected
- **WHEN** a creator opens the Performance tab of the analytics dashboard
- **THEN** every figure is computed from `SurveyEvent` rows in our database

### Requirement: The trust page describes tracking accurately

`/trust/` SHALL NOT claim site-wide absence of cookies or third-party trackers while product
analytics runs on creator-facing pages. The claims SHALL be scoped to the audience they were written
about — survey respondents — and the page SHALL state that creator-facing pages carry product
analytics.

#### Scenario: Cookie and tracker claims are scoped to respondents
- **WHEN** a visitor reads the Data Privacy section of `/trust/`
- **THEN** the no-cookies and no-third-party-tracker claims are stated as applying to survey
  respondents
- **AND** the page discloses that creator-facing pages use product analytics

#### Scenario: PostHog adds nothing to the survey-taking flow
- **GIVEN** `POSTHOG_PROJECT_KEY` is configured
- **WHEN** a respondent loads any page in the survey-taking flow
- **THEN** the set of third-party scripts on that page is unchanged from before this change

Note: the separate claim at line 95 — that the survey-taking flow carries no third-party scripts at
all — is already inaccurate independently of PostHog, because Plausible loads there and fires named
respondent events. This change neither fixes nor worsens it; see the proposal.
