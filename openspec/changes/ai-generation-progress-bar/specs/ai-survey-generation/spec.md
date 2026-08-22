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

The waiting card SHALL present the wait as a progress bar rather than flavour text: an
indeterminate animated bar while nothing has been drafted, and from the first drafted
question a determinate fill computed from questions drafted against a calibrated expected
count, capped below full so the bar can never sit at complete while the draft is still
arriving. The drafted-count caption SHALL accompany the bar. The fill SHALL be computed
server-side and carried by the progress fragment.

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
- **THEN** the endpoint returns a fragment carrying the current counts and the computed bar fill

#### Scenario: Progress has not advanced
- **WHEN** the stored draft counts do not exceed what the client reports having
- **THEN** the endpoint leaves the page untouched rather than re-rendering the waiting card

#### Scenario: Nothing has been drafted yet
- **WHEN** the model is still reasoning and no question has been completed
- **THEN** the bar is indeterminate and no count or fill is shown, rather than a zero that would read as a stalled generation

#### Scenario: Bar fills as questions close
- **WHEN** drafted questions advance from 2 to 4 of an expected 8
- **THEN** the fragment's fill advances proportionally, and the caption states the drafted counts

#### Scenario: Bar never claims completion prematurely
- **WHEN** drafted questions meet or exceed the calibrated expectation while the event is still pending
- **THEN** the fill stays at its cap below full until the success redirect fires
