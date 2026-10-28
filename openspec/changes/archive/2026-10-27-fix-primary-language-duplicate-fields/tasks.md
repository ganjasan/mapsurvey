# Tasks — fix-primary-language-duplicate-fields

## 1. Prerequisites

- [x] 1.1 Archive the completed `ai-survey-generator` change so the `ai-survey-generation`
      capability spec lands in `openspec/specs/` (design D9) — verify our MODIFIED
      requirement header matches the synced main spec
- [x] 1.2 Check migration leaf numbers against open sibling-worktree PRs before picking the
      new migration number (repo convention: parallel migration conflicts)

## 2. Editor — translation inputs and labels

- [x] 2.1 `section_detail_form.html`: render the translations block for
      `available_languages[1:]` only; hide the block entirely when fewer than two languages
- [x] 2.2 `question_form_modal.html`: same rule for the question name/subtext translation
      inputs
- [x] 2.3 Label base title/subheading/name/subtext inputs with the primary language display
      name for multilingual surveys (plain labels for single-language); source display names
      from the survey-content language list
- [x] 2.4 Run the template guard test immediately after the partial edits (repo convention:
      `{# #}` is single-line)

## 3. Editor — choices table

- [x] 3.1 `question_form_modal.html` choices table: remove the `choice-name-default` column;
      render one name column per available language (primary included) for multilingual
      surveys, a single name column for single-language surveys
- [x] 3.2 `serializeChoices()`: emit a flat string for single-language surveys, a per-language
      dict of non-empty columns (primary included) for multilingual; ensure no entered value
      is discarded
- [x] 3.3 Update the row-rendering path (`addChoiceRow`) to populate columns from both flat
      and dict legacy shapes

## 4. Save handlers

- [x] 4.1 `_save_section_translations` / `_save_question_translations`: iterate
      `available_languages[1:]`; ignore `translation_<primary>_*` POST keys
- [x] 4.2 Tests (GIVEN/WHEN/THEN): single-language save creates no translation rows; stale
      primary-language POST is ignored; multilingual save still creates non-primary rows;
      choices save shapes (flat vs dict, primary edit preserved)

## 5. AI generation

- [x] 5.1 `survey/ai/materialize.py` `_translations()`: emit translation rows for
      `languages[1:]` only; choice names flat for single-language, dict (primary included)
      for multilingual
- [x] 5.2 `survey/ai/prompts.py`: add the self-registration/inventory rule to `DESIGN_RULES`;
      reword `USE_CASE_GUIDANCE['citizen_science']` to admit both observation and
      self-registration roles
- [x] 5.3 Update `docs/research/survey-design-rules.md` in the same commit (header contract)
- [x] 5.4 Tests: materialization of `["es"]` brief → no translation rows, flat choice names;
      `["en","it"]` brief → `it` rows only, dicts with both keys

## 6. Data migration

- [x] 6.1 Migration: fold primary-language `SurveySectionTranslation`/`QuestionTranslation`
      rows into base fields ("non-empty translation wins"), delete the rows; log per-survey
      counts
- [x] 6.2 Migration: normalize choice names — flatten dicts on single-language surveys to the
      currently-resolved primary value; add missing primary keys on multilingual surveys with
      the currently-resolved value
- [x] 6.3 Reverse = noop with a comment explaining why (design D6); confirm idempotence
      (second run is a no-op)
- [x] 6.4 Migration tests: divergent base/translation pair resolves to what respondents
      currently see (model on prod surveys 465/467); version-copy surveys are covered
- [ ] 6.5 After deploy: verify `django_migrations` on prod and spot-check surveys 465 and 467
      (section 3 of 465 must read consistently; pt rows on 467 gone)

## 7. Translation completeness indicator

- [x] 7.1 Server-side gap computation for sections/questions/choices per spec (optional texts
      count only when base is non-empty); expose to editor templates
- [x] 7.2 Render the per-entity missing-languages badge in the editor question list and
      section panel; nothing rendered for single-language surveys
- [x] 7.3 Publish flow: non-blocking warning enumerating entities and missing languages in
      the publish confirmation
- [x] 7.4 Tests: untranslated manual question flags all non-primary languages; one missing
      choice key flags that language; fully translated survey publishes without warning

## 8. Verification & delivery

- [x] 8.1 Full test-suite run (`./run_tests.sh survey`) — one baseline, one after-changes,
      summarize delta
- [x] 8.2 Manual pass in the editor: single-language survey (no translation UI), trilingual
      survey (labels, badges, choices columns), publish warning
- [x] 8.3 `openspec validate --strict` for this change; then PR referencing the change
