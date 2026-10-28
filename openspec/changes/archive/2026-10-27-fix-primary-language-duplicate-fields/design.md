## Context

Survey content has two storage layers: base fields (`SurveySection.title/subheading`,
`Question.name/subtext`, `Question.choices` names) and per-language translation rows
(`SurveySectionTranslation`, `QuestionTranslation`, locale dicts inside choice names).
Respondent rendering resolves via `get_translated_*` (survey/models.py:545,643): non-empty
translation wins, else base. `Question.get_choice_name` (models.py:698) resolves dicts by
lang key → `"en"` → first value; flat strings serve every language.

The editor renders a translation input for **every** entry of `available_languages`
(editor_views.py:655,977 iterate the full list; question_form_modal.html renders a
`choice-name-<lang>` column per language *plus* a separate `choice-name-default` column).
So the primary language exists twice everywhere. AI materialization
(`survey/ai/materialize.py:_translations`) fills both copies with identical text; they then
diverge under editing. A third defect sits in `serializeChoices()`
(question_form_modal.html:775): when any language column is non-empty the `default` column's
value is **silently discarded** on save.

Production evidence: survey 465 (single-language es AI draft) — 61 rageclicks, base/translation
text divergence live on the published survey; survey 467 (pt/es/en AI draft) — pt translation
rows byte-identical to base, plus a manually added question with no translation rows shown in
Portuguese to es/en respondents.

The `ai-survey-generation` capability spec currently lives as a delta in the
completed-but-unarchived `ai-survey-generator` change.

## Goals / Non-Goals

**Goals:**

- One storage slot per language: primary language in base fields only; translation rows only
  for `available_languages[1:]`.
- Editor UI that makes the storage model visible: no duplicate inputs, base fields labeled
  with the primary language, translation gaps surfaced instead of silently masked by fallback.
- AI drafts and manual editing produce the same shapes.
- Behavior-preserving data migration for existing surveys (respondents see identical text
  before and after).
- Prompt: stop hard-coding the observer role; support the self-registration/inventory pattern.

**Non-Goals:**

- Machine translation, bulk-translate tooling, or any new translation-authoring UX beyond
  the gap indicator.
- `OptionChoice`/`OptionChoiceTranslation` admin models (legacy path, untouched).
- Changing `get_translated_*` fallback semantics — the fallback stays as the safety net for
  genuinely missing translations.
- Blocking publication on translation gaps (warn only).
- Respondent-side language picker behavior.

## Decisions

### D1. Primary language is `available_languages[0]`

Already the de-facto convention everywhere (editor_views.py:522,879,1329; materialize.py
`primary`). We codify it rather than adding a separate field. Empty `available_languages`
keeps today's semantics: single-language survey, no translation machinery at all.

*Alternative considered*: explicit `primary_language` column — rejected; adds a second source
of truth for something the ordered list already expresses, plus a schema migration for zero
new capability.

### D2. Editor renders translation inputs for `languages[1:]` only; base fields labeled

- Section form (`section_detail_form.html`), question modal, and choices table iterate
  `languages[1:]`. With fewer than two languages the whole translations block disappears —
  this also fixes the existing spec's blind spot (it only exempted **empty**
  `available_languages`, so `["es"]` still got duplicate forms).
- Base inputs get the primary language name in their label (e.g. "Title (Português)") for
  multilingual surveys, so base doesn't read as "neutral default". Single-language surveys
  keep plain labels. Language display names come from the existing survey-content language
  list (the 75-language picker), not Django's UI `LANGUAGES`.

### D3. Choices: drop the `default` column; flat string for single-language, full dict for multilingual

- Single-language survey: one name column; `serializeChoices()` emits a flat string
  (`{"code": 1, "name": "Yes"}`) — matches today's manual single-language output and
  resolves for every respondent via the flat-string path.
- Multilingual survey: one column per language **including primary** (the primary column *is*
  the base slot for choices — there is no separate base field in the JSON, and
  `get_choice_name(code, primary)` resolves by dict key, so the primary key must exist);
  `serializeChoices()` emits a dict over the filled languages.
- The `choice-name-default` column is removed in both modes, which also deletes the
  "default discarded when any language filled" data-loss path.

*Alternative considered*: restructure choice JSON to `{"name": str, "translations": {...}}`
mirroring the model split — rejected; breaks the serialization/export format and every
consumer of `choices` for no respondent-visible gain.

### D4. Save handlers skip the primary language

`_save_section_translations` / `_save_question_translations` iterate `languages[1:]`.
POSTed `translation_<primary>_*` keys (stale open forms, HTMX tails after deploy) are
ignored, so primary rows cannot be resurrected after the migration.

### D5. AI materialization: primary → base only

`_translations()` emits rows for `languages[1:]` only (base already receives
`localized.get(primary)`). Choice names: flat primary string for single-language briefs,
full dict for multilingual — same shapes as D3, so AI-created and manually-created content
are indistinguishable downstream.

### D6. Data migration: fold primary rows into base, "non-empty translation wins"

For every survey with non-empty `available_languages` (canonical *and* version copies —
the migration walks translation rows via their sections/questions, so versions are covered):

1. Sections/questions: for each primary-language row, per field — if the translation value is
   non-empty, write it into the base field (that is what respondents currently see, so the
   move is behavior-preserving); then delete the row.
2. Choices: single-language survey with dict names → flatten each to the value
   `get_choice_name` currently resolves for the primary language. Multilingual survey with a
   dict missing the primary key → insert the primary key with the currently-resolved value.
3. Log per-survey counts of folded rows and overwritten base values.

Forward-only (`RunPython` with `noop` reverse): reversing would need the discarded shadowed
base text, which respondents never saw. The overwritten base text is lost by design; the log
preserves an audit trail in the deploy output.

*Deployment note*: repo convention — verify migration leaf numbers against sibling worktree
PRs before merging, and keep this migration in a commit that does not alter
`preDeployCommand`.

### D7. Translation completeness indicator (capability `translation-completeness`)

Server-computed, no client heuristics:

- For each section/question, `missing_langs` = languages in `languages[1:]` with no row or an
  empty translated name/title; for choice questions, additionally any dict name lacking that
  language key. (Optional fields — `subtext`, `subheading` — count only when the base field
  is non-empty.)
- Editor shows a compact per-entity badge listing missing codes (e.g. "⚠ en, es").
- The publish flow shows a non-blocking warning enumerating the gaps before confirming
  publication. Non-blocking because a partially translated survey is still usable via
  fallback; the point is ending the *silent* masking.

### D8. Prompt tuning: self-registration pattern

- `DESIGN_RULES` ("What to ask about") gains a rule: when the brief implies respondents map
  something they own or represent (their business, project, home, initiative), frame the
  survey in the first person — "register/describe YOUR X" — instead of the observer framing;
  the geo question then collects one primary feature per respondent rather than many
  observations.
- `USE_CASE_GUIDANCE['citizen_science']` is reworded to stop hard-coding "record what they
  observed" as the only role (survey 465: an inventory brief was pushed into a consumer
  survey, costing the creator a rewrite of 2 of 3 sections).
- `docs/research/survey-design-rules.md` is updated in the same commit (prompts.py header
  contract: the doc and the constants must not drift).

### D9. Sequencing with `ai-survey-generator`

That change is 4/4 complete but unarchived, and owns the current `ai-survey-generation`
delta (whose "Multilingual generation in one call" requirement this change modifies).
Archive `ai-survey-generator` (syncing its deltas into `openspec/specs/`) **before** this
change's specs are synced/archived, so our MODIFIED block lands on a main-spec requirement.

## Risks / Trade-offs

- [Migration overwrites base text with translation text] → By construction it promotes the
  respondent-visible value; the shadowed base value was unreachable. Counts logged; the
  migration is idempotent (second run finds no primary rows).
- [Old browser tabs POST `translation_<primary>_*` after deploy] → D4 ignores those keys;
  no rows can be recreated.
- [Multilingual dict missing primary key after user leaves a column blank] → `serializeChoices`
  only stores non-empty values, so a blank primary column yields a dict without the primary
  key; `get_choice_name` falls back to "en"/first value. The completeness badge (D7) flags it;
  we accept the fallback rather than forcing a value.
- [merge-reaches-prod-in-minutes] → Code paths degrade gracefully without the migration
  (fallback still resolves primary rows if any survive); the migration is safe without the
  code (base text respondents see is unchanged). No kill switch needed since neither half
  depends on the other for correctness.
- [Prompt changes shift draft quality in unmeasured ways] → Changes are scoped to role
  framing; `AIGenerationEvent.generated_blob` vs published diffs remain the quality metric to
  watch after deploy.
- [Editor JS (`serializeChoices`, column rendering) is template-inlined and easy to regress]
  → GIVEN/WHEN/THEN tests on the save endpoints (flat vs dict shapes) plus the template guard
  test right after editing partials (repo convention).

## Open Questions

- None blocking. Label wording ("Title (Português)" vs code badge "PT") is an implementation
  detail to settle in the template.
