## MODIFIED Requirements

### Requirement: Asynchronous generation with status polling
A "Generate draft" submission SHALL create an `AIGenerationEvent` row with
`outcome='pending'`, enqueue a Celery task, and return a polling fragment. The page SHALL
poll a status endpoint (HTMX, ~2s interval) that is restricted to the requesting user;
on success the endpoint SHALL respond with an `HX-Redirect` to the populated survey's
editor; on failure it SHALL return a friendly per-outcome message with the form re-enabled
and the brief text preserved.

While the event is pending, the status endpoint SHALL report how much of the draft has actually been
written — counted from the model's own output, never from elapsed time or an assumed number of
steps. It SHALL respond with a progress fragment only when the counts exceed what the polling client
reports already having, and SHALL otherwise leave the page untouched, so the waiting card and its
animations are never re-rendered by a poll that carries no news.

The waiting card SHALL present the wait as a spinner, rotating flavour text, and a live
elapsed-time counter — flavour never implying a pipeline stage the backend does not have,
and no progress bar, percentage or ETA. When drafted counts exist they SHALL be shown as
a plain drafted-counts caption alongside; the flavour line and counter continue
regardless.

The success redirect SHALL carry the generation event's identifier, and the editor SHALL
use it to offer the creator a one-shot feedback prompt on the draft — rendered only when
the identified event belongs to the requesting user and produced the survey being opened,
and only when the analytics snippet is configured. A submitted or dismissed prompt SHALL
not reappear for that draft.

#### Scenario: Successful generation redirects to populated editor
- **WHEN** the generation task completes successfully
- **THEN** the next status poll responds with `HX-Redirect` to `/editor/surveys/<uuid>/` and the survey contains the generated sections and questions with the requesting user as owner collaborator

#### Scenario: Generation still running
- **WHEN** the status endpoint is polled while the event is `pending`
- **THEN** it returns a 200 fragment with an indeterminate spinner and polling continues

#### Scenario: Status endpoint access control
- **WHEN** a user polls the status endpoint for an event created by a different user
- **THEN** the request is rejected (404/403) and no event information is disclosed

#### Scenario: User closes the tab mid-generation
- **WHEN** the creator navigates away while the task runs
- **THEN** the task completes server-side and the created survey appears in the creator's dashboard

#### Scenario: Progress has advanced since the last poll
- **WHEN** the stored draft counts exceed those the polling client reports having
- **THEN** the endpoint returns a fragment carrying the current counts

#### Scenario: Progress has not advanced
- **WHEN** the stored draft counts do not exceed what the client reports having
- **THEN** the endpoint leaves the page untouched rather than re-rendering the waiting card

#### Scenario: Waiting card shows flavour and elapsed time, never a bar
- **WHEN** the waiting card renders
- **THEN** it carries the rotating flavour line and a ticking elapsed counter, and contains no progress bar, percentage or ETA

#### Scenario: Counts render as text when they exist
- **WHEN** a progress fragment arrives with drafted counts
- **THEN** the drafted-counts caption is shown while the flavour line and counter continue

#### Scenario: Feedback prompt on arrival
- **WHEN** the creator lands in the editor via the generation redirect
- **THEN** a dismissible feedback prompt for that draft is shown, once

#### Scenario: Forged draft parameter conjures nothing
- **WHEN** the editor is opened with a draft identifier that is not the requesting user's or did not produce this survey
- **THEN** no feedback prompt is rendered

#### Scenario: Manual surveys never ask
- **WHEN** a survey created manually is opened in the editor
- **THEN** no feedback prompt appears
