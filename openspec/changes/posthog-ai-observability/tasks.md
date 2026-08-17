## 1. Server-side $ai_generation

- [x] 1.1 `emit_llm_generation(event)` in `survey/product_events.py`: `$ai_generation` with `$ai_trace_id='survey-draft-<pk>'`, `$ai_model`, `$ai_provider`, `$ai_input_tokens`, `$ai_output_tokens` (output + reasoning, billing-accurate), separate reasoning property, `$ai_latency` in seconds; never-raises like `emit()`
- [x] 1.2 Failures: `$ai_is_error: true` + outcome slug; no `error_detail` (it can quote model output, which can quote the brief)
- [x] 1.3 Call it from `_emit_terminal_events`, all outcomes except `not_configured` (no provider was reached — nothing to account)
- [x] 1.4 Omit absent values rather than sending zeros

## 2. Redirect and feedback strip

- [x] 2.1 `editor_generation_status` success redirect gains `?draft=<event id>`
- [x] 2.2 `editor_survey_detail` resolves the parameter: strip context only when the event is the requesting user's AND `created_survey` is this survey
- [x] 2.3 Strip partial: thumbs up/down + optional comment, dismissible; renders only when the PostHog key is configured
- [x] 2.4 Client capture of `$ai_feedback` with the trace id, `rating`, optional `comment`; localStorage per draft so reload does not re-ask

## 3. Tests

- [x] 3.1 `$ai_generation` on success: folded output tokens, seconds latency, trace id; no brief/draft/error text among properties
- [x] 3.2 `$ai_generation` on provider_error: error flag + slug, no error message
- [x] 3.3 Redirect carries `?draft=`; forged/foreign/mismatched draft param renders no strip; manual surveys render none
- [x] 3.4 Strip renders for the legitimate owner arriving via the redirect
- [x] 3.5 GIVEN/WHEN/THEN docstrings

## 4. Verification

- [x] 4.1 Full `./run_tests.sh survey`
- [x] 4.2 Live on the dev stand: generate, land with the strip, vote; confirm `$ai_generation` + `$ai_feedback` reach PostHog with one trace id, and PostHog's computed cost is consistent with the measured batch (~$0.007/draft)
