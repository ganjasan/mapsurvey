# creator-funnel-events Specification (delta)

## ADDED Requirements

### Requirement: AI-created surveys emit `survey_created`
A survey materialized by the AI generator SHALL emit `survey_created` with
`creation_method='ai'`, carrying the same properties as the manual path
(`survey_id`, `timestamp_source`). The event SHALL be emitted for the survey's
owner — the creator who submitted the brief — so that it lands on the same person
as their registration and pageviews.

#### Scenario: Successful generation counts as a creation
- **WHEN** an AI draft is materialized successfully
- **THEN** exactly one `survey_created` event is emitted with `creation_method='ai'` and the new survey's id

#### Scenario: Failed generation creates nothing
- **WHEN** a generation ends in `invalid_draft`, `provider_error`, `error` or `not_configured`
- **THEN** no `survey_created` event is emitted, because no survey exists

#### Scenario: Manual path unchanged
- **WHEN** a survey is created through the empty-survey path
- **THEN** `survey_created` still carries `creation_method='manual'` exactly as before

### Requirement: Generated questions count as the question step
A materialized AI draft that contains at least one question SHALL emit
`survey_question_added` with `creation_method='ai'`. The step means "this creator got
past the empty editor", and an AI draft arrives past it without the creator ever
visiting the question-creation view.

#### Scenario: Draft arrives with questions
- **WHEN** an AI draft is materialized with questions
- **THEN** `survey_question_added` is emitted once for that survey, marked `ai`

#### Scenario: Nothing materialized
- **WHEN** a generation fails
- **THEN** no `survey_question_added` is emitted, because no survey exists to have questions

### Requirement: Later funnel events carry the creation method
`survey_published` and `survey_first_response` SHALL carry `creation_method`, resolved
from whether an `AIGenerationEvent` produced the survey. This makes "are AI drafts
published and answered more often?" a breakdown rather than a join back to
`survey_created` through `survey_id`.

#### Scenario: Publishing a generated survey
- **WHEN** a survey produced by the generator is published
- **THEN** `survey_published` carries `creation_method='ai'`

#### Scenario: First response on a manual survey
- **WHEN** a hand-built survey receives its first answer
- **THEN** `survey_first_response` carries `creation_method='manual'`

### Requirement: AI drafting funnel events
The AI generation flow SHALL emit `ai_draft_requested` when a brief is accepted and
enqueued, `ai_draft_finished` when the generation reaches any terminal outcome, and
`ai_draft_opened` when the creator is redirected into the generated survey's editor.
All three SHALL be creator events keyed on the requesting user's primary key.

`ai_draft_finished` SHALL carry `outcome`, and — when the provider reported them —
`latency_ms`, `input_tokens`, `output_tokens`, `provider` and `model`.

#### Scenario: Brief submitted
- **WHEN** a valid brief is accepted and the generation task is enqueued
- **THEN** `ai_draft_requested` is emitted with the number of requested languages and whether a use case was chosen

#### Scenario: Rejected brief emits nothing
- **WHEN** the brief form fails validation, or no provider is configured
- **THEN** no `ai_draft_requested` event is emitted, because no generation was started

#### Scenario: Terminal outcome recorded
- **WHEN** a generation reaches any terminal outcome
- **THEN** exactly one `ai_draft_finished` event is emitted carrying that outcome

#### Scenario: Creator waited for the draft
- **WHEN** the status endpoint issues the `HX-Redirect` into the generated survey's editor
- **THEN** `ai_draft_opened` is emitted once for that generation

### Requirement: Brief content never leaves for analytics
No event SHALL carry the creator's brief text — goal, audience, map target or survey
name — nor any generated survey content. Only counts and categorical values describing
the request SHALL be sent.

#### Scenario: Brief text absent from the payload
- **WHEN** `ai_draft_requested` is emitted for a brief containing free text
- **THEN** none of the brief's free-text values appear in the event properties

### Requirement: Historical AI generations are backfillable
A management command SHALL reconstruct all four events from existing
`AIGenerationEvent` rows, using each row's stored timestamps (`created_at` for the
request, the row's last update for the outcome, `redirected_at` for the open) and the
same deterministic `uuid5` identity and historical-migration client as
`backfill_posthog_events`, so that a re-run cannot double-count.

#### Scenario: Re-running is idempotent
- **WHEN** the backfill command runs twice over the same rows
- **THEN** the second run produces no additional events in PostHog

#### Scenario: Rows without a redirect
- **WHEN** a historical row has no `redirected_at`
- **THEN** no `ai_draft_opened` event is produced for it, rather than one with a substituted timestamp
