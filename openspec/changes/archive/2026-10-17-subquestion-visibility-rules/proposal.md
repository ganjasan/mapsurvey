## Why

Sub-questions in a geo pop-up are always all shown. A pop-up that asks "what kind of place is
this?" cannot follow up differently per kind, so creators build one geo question per kind and copy
the shared follow-ups by hand — 17 point questions × 6 sub-questions on a school mapping survey
(#318), with the copies already drifting. `visibility_rule` exists only on top-level `Question` and
`SurveySection`; the engine admits as controller only an earlier choice question of the section;
the pop-up form is built from `question.subQuestions()` with no filter; and the Visibility block is
not rendered in the sub-question modal at all (issue #338, epic `place-types-in-popup`).

## What Changes

- A sub-question MAY carry a `visibility_rule`. Its controller is an earlier `choice`/`multichoice`
  sub-question of the **same pop-up** (same `parent_question_id`); same rule shape, same any-of
  matching, same fail-open verdicts (`survey/visibility.py`), evaluated **per feature / per object**
  rather than per session.
- Respondent: the pop-up form keeps every sub-question in the DOM and toggles the dependent cards on
  `change` of the controller (inputs disabled while hidden, so they never serialise into the feature
  properties or the `obj__` fields); the section POST re-evaluates the rules server-side for every
  geo feature (from its properties) and every layer object (from its posted fields) and stores no
  answer to a hidden sub-question. Hidden ⇒ never required.
- Editor: the Visibility block renders in the sub-question modal with one group, "This pop-up";
  the branch badge `⑂ if <controller> = <options>` on the sub-question row in the section list and in
  the in-modal sub-question list; the dependents badge `⑂ N` on the controlling sub-question; the
  "Shown when" pill under "Respondent sees"; broken rules badged like top-level ones. The editor's
  section preview toggles pop-up dependents the same way the respondent page does.
- ZIP export already carries the field; import resolves a sub-question rule among the imported
  siblings (remapped codes) and drops an unresolvable one with a report line. Duplication and paste
  remap the rule to the cloned sibling; `publish_draft` keeps it verbatim (codes are kept). A rule
  change on a live survey is structural, as it already is for top-level questions.
- `layer_objects` pop-ups get the behaviour for free (same form, same rule engine); verified by test.

Out of scope (separate issues): the "answered (any option)" condition, question groups, controllers
outside the pop-up (a sub-question ruled by a section question).

## Capabilities

### New Capabilities
- (none)

### Modified Capabilities
- `conditional-visibility`: rules on sub-questions of a geo / Objects-on-the-map question —
  controller scope, per-feature evaluation, client toggling in the pop-up, server-side discard,
  editor authoring and badges, serialization and duplication.

## Impact

- `survey/visibility.py` — `popup_visibility(parent, answers_by_code)`, `popup_controller_options`,
  `describe_rule` for `host_kind='subquestion'`, `lint_rules` reports broken sub-question rules.
- `survey/views.py` — section GET ships pop-up rules; the geo sub-answer loop and
  `_save_object_answers` skip hidden sub-questions.
- `survey/assets/js/conditional_visibility.js` + `base_survey_template.html` — pop-up binding from
  `initPopupFields`; hidden cards' properties pruned on Apply/close.
- `survey/editor_views.py`, `editor/partials/_visibility_block.html`, `question_form_modal.html`,
  `question_list_item.html`, `templatetags/question_utils.py` — modal context, badges, pill.
- `survey/serialization.py::_apply_visibility_rules`, `survey/cloning.py::clone_question`.
- `survey/tests.py` — engine, respondent (geo + objects), editor, serialization, cloning.
- `survey/changelog/2026-10-15-popup-visibility-rules.html`, CLAUDE.md note.
