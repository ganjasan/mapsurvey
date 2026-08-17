## 1. Settings

- [x] 1.1 Add `AI_THINKING_LEVEL` to `mapsurvey/settings.py`, defaulting to `medium` so the setting's introduction changes no behavior; document that an empty string omits `thinkingConfig` entirely
- [x] 1.2 Add `AI_THINKING_LEVEL` to `.env.example` with a comment naming the documented levels (`minimal`/`low`/`medium`/`high`) and the empty-string escape hatch

## 2. Client — request side

- [x] 2.1 Send `generationConfig.thinkingConfig.thinkingLevel` from `GeminiProvider.complete_structured()` when `AI_THINKING_LEVEL` is non-empty
- [x] 2.2 Omit the `thinkingConfig` key entirely when the setting is empty (no `null`, no empty object)

## 3. Client — usage side

- [x] 3.1 Add `thinking_tokens` to `LLMUsage`, defaulting to `None`
- [x] 3.2 Implement the defensive read in the Gemini provider: reasoning-token field when present, else positive `total - prompt - candidates`, else `None`
- [x] 3.3 Confirm the Anthropic provider still constructs a valid `LLMUsage` after the field is added (it reports no reasoning usage, so `None` is correct there)

## 4. Model and migration

- [x] 4.1 Add nullable `thinking_tokens`, `attempts` and `total_latency_ms` to `AIGenerationEvent` in `survey/models.py`
- [x] 4.2 Generate the migration; verify it is additive, nullable, and carries no data migration
- [x] 4.3 Check the migration number does not collide with a leaf on another worktree branch before opening the PR

## 5. Orchestrator accounting

- [x] 5.1 In `generate_survey_draft()`, accumulate attempt count and summed call duration across the retry loop instead of overwriting `usage` each iteration
- [x] 5.2 Sum input and output token counts across the attempt set; take `provider` and `model` from the terminal call
- [x] 5.3 Keep `latency_ms` as the terminal call's own duration
- [x] 5.4 Write the accumulated values in `_finish()`, including on the failure paths so a set that never succeeded is still accounted

## 6. Surfacing

- [x] 6.1 Add the new fields to the `ai_draft_finished` property list in `survey/product_events.py`, omitting each when absent
- [x] 6.2 Add the new fields to the read-only `AIGenerationEvent` admin list in `survey/admin.py`

## 7. Tests

- [x] 7.1 Thinking level is present in the request body when configured, and absent when the setting is empty
- [x] 7.2 Reasoning usage: direct field wins; subtraction fallback when only the total accounts for it; `None` when neither applies (assert `is None`, not falsy — the zero/absent distinction is the point)
- [x] 7.3 Single-attempt generation records `attempts == 1` and `total_latency_ms == latency_ms`
- [x] 7.4 Retried generation records two attempts, summed duration and summed tokens, with `latency_ms` still the terminal call's
- [x] 7.5 A set where every attempt fails still records attempts and summed duration
- [x] 7.6 `ai_draft_finished` carries the new properties and omits absent ones
- [x] 7.7 Write all docstrings in GIVEN/WHEN/THEN

## 8. Verification

- [x] 8.1 Run `./run_tests.sh survey` and compare against the pre-change baseline
- [x] 8.2 Re-read the delta spec against the implementation and tick the tasks
