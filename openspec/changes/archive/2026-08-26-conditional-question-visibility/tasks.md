# Tasks — conditional visibility

## 1. Model and engine

- [x] 1.1 Add `visibility_rule` JSONField (nullable) to `Question` and `SurveySection`
      + migration (check migration-number leaves against master before merge)
- [x] 1.2 Add `CONDITIONAL_VISIBILITY` setting (env-var, default True) in `settings.py`
- [x] 1.3 Create `survey/visibility.py`: `compute_visibility(survey, answers_by_code)`
      → per-question/per-section visibility + visible-section chain; cascade;
      fail-open brokenness check shared with the editor lint (design D2)
- [x] 1.4 Tests (GIVEN/WHEN/THEN): rule match any-of, multichoice controller, section
      AND question, cascade through hidden controller, broken-rule fail-open (each
      brokenness kind), kill switch returns all-visible

## 2. Respondent server side

- [x] 2.1 `survey_section` GET: build the form over visible questions only; embed
      same-section rules as `data-visibility-rules` in the partial context
- [x] 2.2 `survey_section` POST: skip saving answers to questions hidden under the
      submitted state (evaluate POST merged over stored answers) (design D3.1)
- [x] 2.3 POST: after save, purge the session's stored answers to now-hidden questions
      across all sections (geo parents cascade to sub-answers) (design D3.2)
- [x] 2.4 Navigation: next/back resolve through the visible chain (HTMX and
      non-HTMX paths); direct GET of a hidden section redirects like a section miss
- [x] 2.5 Progress: `section_current`/`section_total` computed over the visible chain
- [x] 2.6 Tests: tampered POST discarded, abandoned-branch purge (Area 7 → Area 4),
      hidden-required completes, fan flow-past on uncovered option, back skips hidden,
      direct-URL redirect, progress counts, kill switch restores old behaviour

## 3. Respondent client side

- [x] 3.1 `survey/assets/js/conditional_visibility.js`: idempotent init from
      `data-visibility-rules`, toggle cards + disable hidden inputs on controller
      change, soft reveal; wire into the survey shell and HTMX swaps; collectstatic
- [x] 3.2 Required-summary counts visible questions only
- [x] 3.3 Template-guard test run after template edits (project rule)

## 4. Editor

- [x] 4.1 Shared partial `editor/partials/_visibility_block.html` (mode radio,
      controller picker limited to earlier choice/multichoice grouped by section,
      option checkboxes); include in `question_form_modal.html` and
      `section_detail_form.html`; hide entirely when kill switch off; read-only under
      `is_read_only` with the standard "Create a draft to edit" affordance
- [x] 4.2 Save paths: parse/validate the block in question create/edit and section
      detail POST handlers (autosave-compatible; invalid rule → 422 like other fields)
- [x] 4.3 Condition summary chip in the question modal live preview
- [x] 4.4 Badges: condition chip on conditioned question cards and section rows;
      dependents count on controllers; broken-rule warning badge with tooltip
- [x] 4.5 Uncovered-option lint under the section list (visibility.py helper)
- [x] 4.6 Duplicate/copy: question and section duplicate carry `visibility_rule`;
      cross-survey paste drops it
- [x] 4.7 Live preview renders through the rules (both branches playable)
- [x] 4.8 Tests: save/load rule via editor POSTs, picker excludes later/non-choice
      questions, duplicate carries rule, cross-survey paste drops, lint output,
      broken badge appears after option delete

## 5. Serialization

- [x] 5.1 Export: `visibility_rule` in `_serialize_question` and section serializer
- [x] 5.2 Import: remap `question_code` via `code_remap`; unresolvable rule dropped
      with an import-report line; pre-capability archives import unchanged
- [x] 5.3 Tests: round-trip preserves rule, dropped-rule report, legacy archive

## 6. Verification and rollout

- [x] 6.1 `openspec validate conditional-question-visibility --strict` green;
      full `./run_tests.sh survey` baseline vs after
- [x] 6.2 Manual browser pass of the mockup journeys (UJ-1…UJ-6) on the dev stand,
      including HTMX back/next and a 10-section fan survey
- [x] 6.3 Update `CLAUDE.md` (kill-switch inventory) and backlog item #12 status
