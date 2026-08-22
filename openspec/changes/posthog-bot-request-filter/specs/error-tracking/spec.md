## ADDED Requirements

### Requirement: Bot requests are not captured server-side

Requests whose `User-Agent` header identifies an automated client (crawler, scraper,
HTTP library), or that carry no `User-Agent` header at all, SHALL NOT be tracked by the
server-side PostHog middleware: no context is opened for them and no exception raised
while serving them is captured. The classification MUST happen at the request-filter
stage, before tag scrubbing, because on respondent surfaces the user-agent tag is
removed prior to capture and cannot be classified downstream.

Human-looking browser user-agents SHALL continue to be tracked exactly as before.

#### Scenario: Crawler-triggered exception is not captured
- **GIVEN** `POSTHOG_PROJECT_KEY` is configured
- **WHEN** a request with a Googlebot user-agent raises `Http404` on a draft survey URL
- **THEN** the request filter excludes the request and no exception event is captured

#### Scenario: Missing user-agent is treated as a bot
- **GIVEN** `POSTHOG_PROJECT_KEY` is configured
- **WHEN** a request arrives with no `User-Agent` header
- **THEN** the request filter excludes the request

#### Scenario: Browser requests keep being tracked
- **GIVEN** `POSTHOG_PROJECT_KEY` is configured
- **WHEN** a request arrives with an ordinary desktop-browser user-agent
- **THEN** the request filter includes the request, subject to the existing
  `/admin/` and `/__debug__/` exclusions
