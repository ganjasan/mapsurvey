## ADDED Requirements

### Requirement: The browser reaches PostHog through a configurable first-party host

The system SHALL read a `POSTHOG_CLIENT_HOST` setting from the environment and SHALL initialise the
browser snippet's `api_host` against it. When `POSTHOG_CLIENT_HOST` is empty or unset, the system
SHALL fall back to `POSTHOG_API_HOST`, so that a deployment which has not provisioned a proxy
behaves exactly as it did before the setting existed.

The setting SHALL carry a full origin (scheme and host), so that the proxy hostname can be changed
— or abandoned — without a code change.

#### Scenario: Configured proxy host is what the browser talks to
- **GIVEN** `POSTHOG_PROJECT_KEY` is configured
- **AND** `POSTHOG_CLIENT_HOST` is set to a first-party origin
- **WHEN** a tracked page is requested
- **THEN** the rendered snippet initialises `api_host` against that origin
- **AND** the response body contains no reference to `eu.i.posthog.com`

#### Scenario: Unconfigured proxy falls back to the API host
- **GIVEN** `POSTHOG_PROJECT_KEY` is configured
- **AND** `POSTHOG_CLIENT_HOST` is empty
- **WHEN** a tracked page is requested
- **THEN** the rendered snippet initialises `api_host` against `POSTHOG_API_HOST`

#### Scenario: Proxy host does not resurrect the snippet on excluded surfaces
- **GIVEN** `POSTHOG_PROJECT_KEY` and `POSTHOG_CLIENT_HOST` are both configured
- **WHEN** a respondent requests a page under `/surveys/` or `/r/`
- **THEN** the response body contains no PostHog snippet and no reference to the proxy host

#### Scenario: Unconfigured key renders nothing regardless of the proxy
- **GIVEN** `POSTHOG_PROJECT_KEY` is empty
- **AND** `POSTHOG_CLIENT_HOST` is set
- **WHEN** a tracked page is requested
- **THEN** the response body contains no PostHog snippet and no reference to the proxy host

### Requirement: Server-side capture stays on the direct PostHog host

The server-side PostHog client SHALL be configured with `POSTHOG_API_HOST` and SHALL NOT use
`POSTHOG_CLIENT_HOST`. Django view exceptions and Celery task failures SHALL therefore reach PostHog
without traversing the browser proxy, whose only purpose is to defeat client-side blocking.

#### Scenario: The Python SDK ignores the proxy host
- **GIVEN** `POSTHOG_PROJECT_KEY` is configured
- **AND** `POSTHOG_CLIENT_HOST` is set to a first-party origin different from `POSTHOG_API_HOST`
- **WHEN** the application configures the server-side client at startup
- **THEN** the client's host is `POSTHOG_API_HOST`

#### Scenario: Error capture is unaffected by proxy configuration
- **GIVEN** `POSTHOG_CLIENT_HOST` is set
- **WHEN** a view raises an unhandled exception
- **THEN** the exception is reported through the server-side client exactly as before this change

### Requirement: The PostHog UI host is stated explicitly

The rendered snippet SHALL initialise with `ui_host` set to the PostHog Cloud EU application origin,
so that toolbar and "open in PostHog" links resolve to PostHog rather than to whichever host the
snippet was pointed at.

#### Scenario: UI host is present in the rendered config
- **GIVEN** `POSTHOG_PROJECT_KEY` is configured
- **WHEN** a tracked page is requested
- **THEN** the rendered snippet's initialisation sets `ui_host` to the PostHog Cloud EU application
  origin
- **AND** it does so whether or not `POSTHOG_CLIENT_HOST` is configured

### Requirement: Snippet assets load from the same host as the events

The snippet's JavaScript asset SHALL be fetched from the host the snippet is initialised against, so
that a blocked asset host cannot defeat an unblocked event host. When no proxy is configured, the
asset host SHALL remain PostHog's dedicated asset domain, as today.

#### Scenario: Assets follow the proxy host
- **GIVEN** `POSTHOG_CLIENT_HOST` is set to a first-party origin
- **WHEN** a tracked page is rendered and loaded in a browser
- **THEN** the PostHog JavaScript asset is requested from that origin and returns success

#### Scenario: Assets keep the PostHog asset domain without a proxy
- **GIVEN** `POSTHOG_CLIENT_HOST` is empty
- **WHEN** a tracked page is rendered
- **THEN** the asset reference resolves to PostHog's asset domain, unchanged from before this change

### Requirement: The trust page states who carries analytics traffic

`/trust/` SHALL name Cloudflare as the CDN and reverse proxy fronting the hosted service, rather
than referring to it solely as the anti-abuse challenge vendor. Where the page describes product
analytics, it SHALL distinguish where the data is stored from where it transits, and SHALL NOT claim
a guarantee about transit geography that the provider does not give.

#### Scenario: Cloudflare's role is stated in hosting, not only in abuse defenses
- **WHEN** a visitor reads the Hosting & Data Residency section of `/trust/`
- **THEN** the page states that Cloudflare fronts the hosted service as CDN and reverse proxy
- **AND** states that this includes product-analytics traffic

#### Scenario: Storage and transit are distinguished
- **WHEN** a visitor reads what `/trust/` says about product analytics
- **THEN** the page states that the data is stored in the EU (PostHog Cloud EU)
- **AND** states that transit passes over Cloudflare's network without a contractual guarantee of
  EU-only termination

#### Scenario: Respondent claims are unchanged
- **WHEN** a visitor reads what `/trust/` says about the survey-taking flow
- **THEN** the statement that product analytics never loads where respondents answer surveys is
  still present and still true of the shipped configuration
