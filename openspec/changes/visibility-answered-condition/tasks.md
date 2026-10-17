## 1. Engine

- [x] 1.1 `survey/visibility.py`: `ANY_ANSWER`, `rule_mode()`, `rule_matches()`, `client_rule()`;
      `_rule_verdict` answered branch; walks, `popup_visibility`, `popup_rules_for_client`,
      `describe_rule`/`_describe_verdict`, `lint_rules` coverage use them; module docstring.
- [x] 1.2 Tests `VisibilityEngineTest` / `PopupVisibilityEngineTest`: answered rule hidden on
      no answers, shown on any option (incl. a code not in the rule), option added later still
      matches, cascade through hidden controller, broken on missing/non-choice/forward
      controller, label text, lint has no uncovered options and no broken verdict.

## 2. Respondent and preview

- [x] 2.1 `views._build_section_context` and `editor_section_preview`: client rules through
      `client_rule`; `conditional_visibility.js` answered branch.
- [x] 2.2 Tests `ConditionalVisibilityRespondentTest`: a section ruled "ZONE answered" is skipped
      on a fresh session and reached after any zone; progress counts it only when shown;
      same-section rule reaches the client in the answered shape.

## 3. Editor

- [x] 3.1 `_parse_visibility_rule`: `visibility_match`; `_visibility_block_context`:
      `visibility_rule_match`.
- [x] 3.2 `_visibility_block.html`: match select, help line, script toggles; existing styles.
- [x] 3.3 Tests `ConditionalVisibilityEditorTest`: POST answered → stored shape without codes,
      POST any_of unchanged, absent `visibility_match` = any_of, block renders the saved mode,
      badge/pill text.

## 4. Import, funnel, docs

- [x] 4.1 `serialization._apply_visibility_rules`: answered shape on sections, questions and
      sub-questions; tests: old shape and new shape round-trip, archive without the key unchanged.
- [x] 4.2 `analytics._section_rules` / `_eligible_sessions`: answered sections; test.
- [x] 4.3 `models.py` help texts; help article step 5. No changelog entry: the epic #343
      ships one entry for all of its changes (owner decision 2026-10-15).
- [x] 4.4 Full `survey` suite green (2651 tests, 2026-10-15).
