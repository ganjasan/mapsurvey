## Context

A geo answer (point/line/polygon) is one `Answer` with geometry. In Mapsurvey the *attributes* of that geometry are captured as **sub-answers**: `Answer.parent_answer` points from a sub-answer back to the geo answer, and `Question.parent_question` links a sub-question to the geo question. The public-results geo popup ignored this and instead joined selected top-level questions by `survey_session_id`, which is both the wrong data (unrelated form questions) and the wrong granularity (per session, not per point).

## Goals

- Popup fields = the geo question's sub-questions; popup values = that point's own sub-answers.
- No schema change; `geo_label_fields` stays a list of question codes.
- Privacy unchanged: creator opt-in per field, no free text, no session id / IP / timestamp.

## Decisions

### D1: Popup fields are the geo question's sub-questions (non-text)
The editor lists `Question.objects.filter(parent_question=block.question).exclude(input_type in TEXT_INPUT_TYPES)`, ordered by `order_number`. Text sub-questions are omitted (free text is never published). A geo question with no eligible sub-questions renders an empty state and the popup is anonymous geometry only.

### D2: Per-point join via `parent_answer`
`_map_payload` collects, for the visible geo answers, their sub-answers in one query:
`Answer.objects.filter(parent_answer_id__in=<geo answer ids>, question__code__in=label_codes, survey_session_id__in=clean_ids)`, grouped by `parent_answer_id`. Each feature's `properties` come only from its own sub-answers (`question.name → display value`). This replaces the session keyed `_collect_label_values`.

### D3: Reuse `_answer_display_value`
Sub-answer values are rendered by the existing `_answer_display_value` (choice/multichoice/rating → choice names; number/range → numeric; text → None, so it self-excludes even if a text sub-question code slipped in). No new value logic.

### D4: `geo_label_fields` semantics widen, format unchanged
It still stores question codes; they now refer to sub-question codes. Old stored top-level codes simply match no sub-answers and produce empty properties — safe for the small amount of beta-era data.

## Risks / Trade-offs

- **Existing configured blocks lose their (session-join) popup fields** because those codes were top-level. Acceptable: the feature is beta with little prod data, and the old behavior was the bug being fixed. Not silently reinterpreted — old codes just yield nothing until re-picked.
- **Session-level context (demographics on every point)** is intentionally dropped, not ported. If a real need appears, it returns later as an explicit, clearly-labeled "respondent context (same for all of a respondent's points)" group — out of scope here.

## Migration Plan

No data migration. Behavior-only + template/context. Reversible by restoring `_collect_label_values` and the top-level picker.
