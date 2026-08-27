## ADDED Requirements

### Requirement: Editor preview surfaces are never tracked

The system SHALL NOT render the PostHog snippet for a request whose resolved URL name appears in
`POSTHOG_EXCLUDED_VIEW_NAMES`, regardless of whether `POSTHOG_PROJECT_KEY` is configured. That
list SHALL cover the editor's section preview and thanks preview: the editor renders respondent
pages inside preview iframes served from under `/editor/`, so the path-prefix exclusion that
protects respondent surfaces cannot reach them.

The exclusion SHALL be enforced where the template context is built, alongside the path-prefix
exclusion, so that a preview template added later inherits the behaviour instead of depending on
which base template its author copied.

A page whose URL cannot be resolved to a view name SHALL be treated as not excluded, so an
unresolved request never silently loses tracking it was supposed to have.

#### Scenario: Section preview is not tracked

- **GIVEN** `POSTHOG_PROJECT_KEY` is configured
- **WHEN** a creator's browser loads the editor section preview for a survey
- **THEN** the response body contains no PostHog snippet

#### Scenario: Thanks preview is not tracked

- **GIVEN** `POSTHOG_PROJECT_KEY` is configured
- **WHEN** a creator's browser loads the editor thanks preview for a survey
- **THEN** the response body contains no PostHog snippet

#### Scenario: The editor page framing the preview is still tracked

- **GIVEN** `POSTHOG_PROJECT_KEY` is configured
- **WHEN** the creator requests the editor page that hosts the preview pane
- **THEN** the response body contains the PostHog snippet

### Requirement: A framed document does not start a second PostHog client

Where the snippet is rendered at all, it SHALL initialise PostHog only when the document is the
top-level document of its tab. A document rendered inside a frame SHALL start no PostHog client,
capture no page view and record no session, independently of the server-side exclusions above.

The reason is that two PostHog clients in one browser tab write into one session: the recorder
inside a preview iframe emits its own viewport and its own page views, which makes a session
recording alternate between two layouts and multiplies `$pageview` counts for the surrounding
page.

#### Scenario: Framed document starts no client

- **GIVEN** a tracked page is loaded inside an iframe
- **WHEN** the snippet runs
- **THEN** no PostHog client is initialised for that document

#### Scenario: Top-level document is unaffected

- **GIVEN** a tracked page is loaded as the top-level document
- **WHEN** the snippet runs
- **THEN** PostHog is initialised as before, including the page view and any identify call
