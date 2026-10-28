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

#### Scenario: Feedback prompt on arrival
- **WHEN** the creator lands in the editor via the generation redirect
- **THEN** a dismissible feedback prompt for that draft is shown, once

#### Scenario: Forged draft parameter conjures nothing
- **WHEN** the editor is opened with a draft identifier that is not the requesting user's or did not produce this survey
- **THEN** no feedback prompt is rendered

#### Scenario: Manual surveys never ask
- **WHEN** a survey created manually is opened in the editor
- **THEN** no feedback prompt appears

### Requirement: Generation event log
Every generation attempt SHALL write one `AIGenerationEvent` row carrying `kind`
(`survey_draft`), user, organization, brief, languages, provider, model, token usage,
latency, outcome (`pending/success/not_configured/provider_error/invalid_draft/error`),
error detail, and the created survey FK on success. The model SHALL be registered
read-only in Django admin. `check_quota(organization, kind)` SHALL exist as a documented
no-op precondition called before any provider call.

The row SHALL additionally make a retried generation distinguishable from a single slow one. It
SHALL carry the number of provider calls the attempt set started, the summed duration of those
calls that reported one, and reasoning-token usage. `latency_ms` SHALL keep its existing meaning —
the duration of the terminal provider call — so rows written before this requirement remain readable
as measured. Input, output and reasoning token counts SHALL be summed across the attempt set, since
that is what the generation cost, with reasoning remaining absent until at least one call reports
it; `provider` and `model` SHALL be those of the terminal call.

These fields SHALL ride the existing `ai_draft_finished` analytics event, each omitted when absent,
so the split is a breakdown rather than a join back to the database.

Every finished attempt-set SHALL additionally emit one analytics event in the LLM-analytics
schema (`$ai_generation`), carrying a stable trace identifier derived from the row, model,
provider, token counts and latency in seconds — and NEVER content: no brief text, no draft
text, and no provider error message (which can quote model output). Reasoning tokens SHALL
be folded into the reported output tokens, because the provider bills them at the output
rate and the computed cost must equal the invoice; the reasoning share SHALL also be
reported separately. Failures SHALL emit with an error flag and the outcome slug only. A
creator's feedback on a draft SHALL be captured against the same trace identifier
(`$ai_feedback`), so the verdict attaches to the exact generation it judges.

#### Scenario: Success is measurable
- **WHEN** a generation succeeds
- **THEN** its event row has `outcome='success'`, non-null token counts and latency, and links to the created survey

#### Scenario: Quota seam spends no tokens
- **WHEN** `check_quota` raises `QuotaExceeded` (future #87 behavior)
- **THEN** no provider call is made and the event outcome is recorded without token spend

#### Scenario: Single-attempt generation
- **WHEN** the first provider call returns a draft that passes validation
- **THEN** the row records one attempt and its summed duration equals `latency_ms`

#### Scenario: Retried generation is not reported as one fast call
- **WHEN** the first provider call is rejected by validation and a second call succeeds
- **THEN** the row records two attempts, a summed duration covering both calls, and summed token counts, while `latency_ms` remains the second call's own duration

#### Scenario: Failure after retry is accounted too
- **WHEN** every attempt in the set fails or is rejected
- **THEN** the row still records the attempt count and the summed duration of the calls that were made

#### Scenario: Analytics carries the new measurements
- **WHEN** `ai_draft_finished` is emitted for a generation that has reasoning usage and an attempt count
- **THEN** those properties are present on the event, and properties without a value are omitted rather than sent as zero

#### Scenario: LLM analytics event on success
- **WHEN** a generation succeeds having spent input, output and reasoning tokens
- **THEN** one `$ai_generation` event is captured whose output-token count is the sum of output and reasoning tokens, whose latency is in seconds, and which carries no brief, draft or error text

#### Scenario: LLM analytics event on failure
- **WHEN** a generation ends in `provider_error`
- **THEN** one `$ai_generation` event is captured flagged as an error with the outcome slug, and the provider's error message is not among its properties

#### Scenario: Feedback lands on the trace
- **WHEN** the creator votes on a generated draft
- **THEN** an `$ai_feedback` event carries the same trace identifier as the generation's `$ai_generation` event
