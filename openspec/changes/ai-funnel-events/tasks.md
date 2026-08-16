# Tasks

## 1. Event vocabulary

- [x] 1.1 `survey/product_events.py`: add `AI_DRAFT_REQUESTED`, `AI_DRAFT_FINISHED`, `AI_DRAFT_OPENED` constants next to the creator-funnel ones, documented with the `AIGenerationEvent` field each backfills from
- [x] 1.2 Keep `CREATION_AI` where it is — it stops being a dead constant once generation.py uses it

## 2. Forward emission

- [x] 2.1 `survey/ai/generation.py` `_finish()`: emit `ai_draft_finished` with outcome and, when usage is present, provider/model/tokens/latency
- [x] 2.2 Same place, on `outcome='success'`: emit `survey_created` with `creation_method=CREATION_AI` and the new survey's id, for `event.user_id`
- [x] 2.2b Same place: emit `survey_question_added` when the materialized survey has questions (issue #76 — otherwise the funnel shows the AI arm stuck at the empty-editor step)
- [x] 2.2c `product_events.creation_method_for()` + use it in `survey_published` (editor_views) and `survey_first_response` (signals), so the split is a breakdown rather than a join
- [x] 2.2d `backfill_posthog_events`: pass the resolved method to every survey-scoped event and stop defaulting `creation_method` on user-scoped ones
- [x] 2.3 `survey/editor_views.py` `_start_survey_generation()`: emit `ai_draft_requested` after `start_generation()` — never before, so a failed enqueue cannot leave a request with no generation
- [x] 2.4 `survey/editor_views.py` `editor_generation_status()`: emit `ai_draft_opened` where `redirected_at` is stamped, only on the transition (a re-poll must not emit twice)

## 3. Backfill

- [x] 3.1 `survey/management/commands/backfill_ai_events.py`: reconstruct all four events from `AIGenerationEvent`, reusing the `uuid5` scheme and the historical-migration client of `backfill_posthog_events`
- [x] 3.2 `--dry-run`, `--since`, `--limit`, oldest-first ordering — same contract as the existing command
- [x] 3.3 Refuse to send person properties from this command, same guard as the existing one (PostHog applies `$set` regardless of event timestamp)

## 4. Tests (GIVEN/WHEN/THEN, survey/tests.py)

- [x] 4.1 Successful generation emits `survey_created` with `creation_method='ai'` and the survey id
- [x] 4.2 Each failing outcome emits `ai_draft_finished` with that outcome and no `survey_created`
- [x] 4.3 Manual creation still emits `creation_method='manual'` (regression guard on the shared event)
- [x] 4.4 `ai_draft_requested` fires on accepted brief; not on invalid form, not when the provider is unconfigured
- [x] 4.5 Brief free text (goal/audience/map target/name) appears in no event payload
- [x] 4.6 `ai_draft_opened` fires once on the redirecting poll and not on a repeat poll
- [x] 4.7 Backfill: idempotent second run, rows without `redirected_at` produce no open event
- [x] 4.8 Full suite `./run_tests.sh survey` — one baseline, one after-changes

## 5. Production

- [ ] 5.1 Run `backfill_ai_events --dry-run` against production, compare counts with `AIGenerationEvent` rows directly
- [ ] 5.2 Run it for real, then reconcile: events in PostHog == rows in the database, per outcome
