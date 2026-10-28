## ADDED Requirements

### Requirement: Server-side exceptions are captured when configured

When `POSTHOG_PROJECT_KEY` is set, unhandled exceptions raised while serving a Django request SHALL
be captured to PostHog with the exception type, message and stack trace. For requests from an
authenticated user, the capture SHALL carry the user's primary key as the distinct id so the error
joins the person timeline the analytics snippet already writes.

When `POSTHOG_PROJECT_KEY` is empty (the default), the PostHog client SHALL be explicitly disabled:
no capture call, from any code path, may produce a network request.

#### Scenario: View exception is captured with the creator's identity
- **GIVEN** `POSTHOG_PROJECT_KEY` is configured AND a creator is signed in
- **WHEN** a view raises an unhandled exception
- **THEN** an exception event is captured carrying the creator's primary key as distinct id

#### Scenario: Unconfigured key disables capture entirely
- **GIVEN** `POSTHOG_PROJECT_KEY` is empty
- **WHEN** any exception is raised anywhere in the application
- **THEN** nothing is sent to PostHog and no error is raised by the reporting path itself

### Requirement: Celery task failures are captured

When `POSTHOG_PROJECT_KEY` is set, a Celery task that fails SHALL be captured to PostHog with the
task name and task id attached. The reporting path SHALL NOT raise: a failure inside the error
reporter must not affect the worker or the task result.

#### Scenario: Failing task is reported with its name
- **GIVEN** `POSTHOG_PROJECT_KEY` is configured
- **WHEN** a Celery task raises
- **THEN** an exception event is captured tagged with the task's name and id

#### Scenario: Reporter failure is swallowed
- **WHEN** the capture call itself raises
- **THEN** the task failure handling completes normally and the worker continues

### Requirement: Errors on respondent surfaces carry no respondent-describing metadata

Exceptions raised on paths under `POSTHOG_EXCLUDED_PREFIXES` SHALL still be captured — they are our
defects — but the captured event SHALL NOT include the respondent's IP address or user-agent, and
SHALL truncate the URL and path to the excluded prefix so no survey-identifying slug is transmitted.

Requests under `/admin/` and `/__debug__/` SHALL NOT be captured at all.

#### Scenario: Respondent-page error is captured scrubbed
- **GIVEN** `POSTHOG_PROJECT_KEY` is configured
- **WHEN** a view under `/surveys/` raises
- **THEN** an exception event is captured
- **AND** it contains no `$ip` and no `$user_agent` tag
- **AND** its URL and path tags are truncated to `/surveys/`

#### Scenario: Admin errors are not reported
- **WHEN** a view under `/admin/` raises
- **THEN** no exception event is captured

### Requirement: The SDK version is pinned against known-broken releases

The `posthog` Python dependency SHALL be pinned to the 6.9 series, and the codebase SHALL assert at
test time that `PosthogContextMiddleware.process_exception` exists. Releases 6.7.5–6.7.13 shipped
without working exception capture, and 7.x requires Python ≥3.10, which this project does not run.

#### Scenario: Middleware exception hook exists
- **WHEN** the test suite runs
- **THEN** a test fails if the installed SDK's Django middleware lacks `process_exception`
