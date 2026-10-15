## 1. Engine

- [x] 1.1 `survey/visibility.py`: `popup_visibility(parent, answers_by_code, enabled=None)` →
      `PopupVisibility(question_visible, broken)`; sibling index + `_rule_verdict` (D2);
      `popup_controller_options(parent, host=None)`; `describe_rule` for `host_kind='subquestion'`;
      `lint_rules` adds broken sub-question rules.
- [x] 1.2 Tests `PopupVisibilityEngineTest`: no rule, any-of, unanswered, cascade inside the pop-up,
      broken (section controller, forward, non-choice, gone options), kill switch.

## 2. Respondent

- [x] 2.1 `views._build_section_context`: `popup_visibility_rules_json` (flat by sub code, valid
      rules only); `survey_section_partial.html` `data-popup-visibility-rules`.
- [x] 2.2 Section POST: geo sub-answer loop skips hidden sub-questions per feature;
      `_save_object_answers` skips per object.
- [x] 2.3 `conditional_visibility.js`: `window.ConditionalVisibility.bindPopup(formEl)`; called from
      `initPopupFields`; `base_survey_template.html` prunes hidden cards' properties on
      Apply/close.
- [x] 2.4 `editor_views.editor_section_preview`: ship the same pop-up rules.
- [x] 2.5 Tests `PopupVisibilityRespondentTest`: GET ships rules, discard on geo feature, two
      features independent, discard on object, kill switch stores everything.

## 3. Editor

- [x] 3.1 `_visibility_block_context(..., 'subquestion', host, parent)`; `editor_subquestion_create`
      (GET + error renders) and `editor_question_edit` (sub-question branches) pass it.
- [x] 3.2 `_visibility_block.html`: group label from `title|default:name` works for the namespace;
      empty-groups copy for pop-ups.
- [x] 3.3 `question_utils.visibility_info` resolves `'subquestion'`; in-modal sub-question list gets
      the branch + dependents badges.
- [x] 3.4 Tests `PopupVisibilityEditorTest`: block rendered with siblings only, rule saved via
      sub-question create and edit, badges in the list and modal, pill, live survey refuses.

## 4. Serialization and duplication

- [x] 4.1 `serialization._apply_visibility_rules`: sibling pass with remap and report line.
- [x] 4.2 `cloning.clone_question`: remap sub-question rules to cloned siblings.
- [x] 4.3 Tests: ZIP round trip with collision, duplicate, cross-survey paste keeps, publish_draft keeps.

## 5. Wrap-up

- [x] 5.1 Changelog entry `survey/changelog/2026-10-15-popup-visibility-rules.html`.
- [x] 5.2 CLAUDE.md: one paragraph under Conditional visibility.
- [x] 5.3 Run `./run_tests.sh survey.tests.<new classes>` and the existing visibility classes;
      template-comment guard test.
