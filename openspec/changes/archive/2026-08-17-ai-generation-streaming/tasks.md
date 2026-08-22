## 1. Progress scanner

- [x] 1.1 Create `survey/ai/progress.py` with a `DraftProgress` scanner fed accumulated text, reporting closed section and question counts
- [x] 1.2 Track string and escape state so braces inside creator-visible text cannot be miscounted
- [x] 1.3 Keep the module free of HTTP, Django and provider specifics so it is testable by handing it strings

## 2. Provider contract

- [x] 2.1 Add `on_progress=None` to `complete_structured` on both providers
- [x] 2.2 Swallow exceptions raised by the callback — a progress failure must never fail a draft
- [x] 2.3 Wire the Anthropic provider's existing internal stream to the callback

## 3. Gemini streaming

- [x] 3.1 Use the streaming endpoint with SSE when a callback is supplied; keep the existing non-streaming path when it is not
- [x] 3.2 Check response status before consuming the body, and normalize a mid-stream failure to `ProviderError`
- [x] 3.3 Accumulate chunk text, feed the scanner, and assemble the same final JSON the non-streaming path produces
- [x] 3.4 Read `usageMetadata` from the final chunk; a stream that dies without one records no usage, as a connection error does today
- [x] 3.5 Preserve the `MAX_TOKENS` finish-reason check that raises `TruncatedOutput`

## 4. Model and migration

- [x] 4.1 Add nullable `sections_drafted` and `questions_drafted` to `AIGenerationEvent`
- [x] 4.2 Generate the migration; verify additive, nullable, no data migration
- [x] 4.3 Re-check the migration number against leaves on other branches

## 5. Orchestrator wiring

- [x] 5.1 Pass a progress callback from `generate_survey_draft` that writes counts to the event row
- [x] 5.2 Write with `queryset.update()` on changed fields only, and only when a count advances
- [x] 5.3 Reset counts at the start of each attempt so a retry does not appear to continue the previous draft

## 6. Status endpoint

- [x] 6.1 While pending, compare stored counts against what the poller reports having and return a progress fragment only when they advanced
- [x] 6.2 Keep returning 204 when nothing changed, and keep the terminal success/failure branches untouched
- [x] 6.3 Keep `last_polled_at` stamping exactly as it is

## 7. Overlay

- [x] 7.1 Add a progress element inside the card that the poller targets, leaving the card, spinner and fade-in untouched
- [x] 7.2 Have the poller send the counts it already has
- [x] 7.3 Show nothing until the first section closes, so a reasoning model does not display a stalled zero
- [x] 7.4 Keep the quips; rewrite the template comment to record that the no-fabricated-stages rule still holds and why the counter satisfies it

## 8. Tests

- [x] 8.1 Scanner: counts sections and questions as text arrives in arbitrary chunk splits
- [x] 8.2 Scanner: braces and quotes inside label text do not affect counts
- [x] 8.3 Scanner: partial trailing object is not counted until it closes
- [x] 8.4 Provider: callback invoked while streaming, and the returned blob and usage match the non-streaming result
- [x] 8.5 Provider: a raising callback does not fail the generation
- [x] 8.6 Provider: no callback means no behavior change
- [x] 8.7 Provider: mid-stream failure surfaces as `ProviderError`
- [x] 8.8 Endpoint: fragment when counts advanced, 204 when not, terminal branches unchanged
- [x] 8.9 Endpoint: access control still rejects another user's event
- [x] 8.10 Orchestrator: counts written as they advance; a retry restarts them
- [x] 8.11 Write all docstrings in GIVEN/WHEN/THEN

## 9. Verification

- [x] 9.1 Run `./run_tests.sh survey` against the pre-change baseline
- [x] 9.2 Re-read the delta spec against the implementation and tick the tasks
