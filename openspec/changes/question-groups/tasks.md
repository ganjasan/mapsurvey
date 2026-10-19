## 1. Mockup (gate before templates)

- [x] 1.1 Static mockup `openspec/changes/question-groups/question-groups.mockup.html`: the three
      display styles in a section and in a geo pop-up (desktop + 390 px, light + dark), the editor
      group row with nested questions, the group modal with "Respondent sees". Owner approves
      before 4.x / 6.x templates are written.

## 2. Model and helpers

- [x] 2.1 `survey/models.py`: `QuestionGroup`, `QuestionGroupTranslation`, `Question.group`
      (SET_NULL, `related_name='questions'`), `CommentThread.group_code` + `'group'` anchor choice
      and constraint branch; `get_translated_title/description`; `QuestionGroup.clean()` invariants
      (D1). Migration `0099` (check `origin/master` for a parallel `0099` first).
- [x] 2.2 `survey/groups.py`: `group_runs(questions, groups)` (D2, degrades on non-contiguous
      members), `groups_for(section, parent=None)`, `next_order(section, parent)`,
      `shift_down(section, parent, after)`, code generation unique per survey.
- [x] 2.3 Tests `QuestionGroupModelTest`: SET_NULL keeps members in place, `group_runs` normal and
      degraded, `next_order` counts groups, code uniqueness, translation fallback.

## 3. Visibility engine

- [x] 3.1 `survey/visibility.py`: host kind `'group'` — `compute_visibility` (`group_visible`,
      member AND), `popup_visibility` (per feature), client rules keyed `group:<code>`,
      `lint_rules`, `describe_rule`, `controller_options` / `popup_controller_options` (members
      excluded), dependents count.
- [x] 3.2 Tests `GroupVisibilityEngineTest`: no rule, any-of, answered mode, cascade into a later
      question controlled by a member, member rule on top, controller inside the group = broken,
      forward controller = broken, pop-up per-feature independence.

## 4. Respondent

- [x] 4.1 `forms.SurveySectionAnswerForm.field_runs`; `partials/question_fields.html` iterates runs;
      new `partials/question_group.html` (plain / card / collapsible, escaped title, `|safe`
      sanitized description, translated text).
- [x] 4.2 `views._build_section_context`: groups with members hidden from earlier sections are not
      rendered; same-section group rules into `visibility_rules_json`, pop-up group rules into
      `popup_visibility_rules_json`; pop-up HTML per parent renders groups.
- [x] 4.3 Section POST: hidden-group members discarded and purged through `question_visible`
      (geo features and `_save_object_answers` via `_popup_visibility_for`) — verify, add only
      what is missing.
- [x] 4.4 `conditional_visibility.js`: `group:<code>` keys toggle `.question-group[data-group-code]`
      and disable its inputs; `hiddenFieldNames` includes members of hidden groups so geo
      properties are pruned on Apply/close.
- [x] 4.5 `base_survey_template.html`: collapsible toggle (bound in sections and `initPopupFields`),
      submit-time required check opens a closed group before focusing; respondent CSS for the three
      styles with dark-mode tokens.
- [x] 4.6 `editor_section_preview` renders groups and ships group rules (reuse respondent helpers).
- [x] 4.7 Tests `GroupRespondentTest`: section GET renders a card group with its questions in
      order; pop-up HTML contains the group; acceptance — "Your visit" with three sub-questions and
      rule "Type of place answered" ships the rule, POST without a type stores none of the three,
      with a type stores three answers; two features independent; layer-object pop-up; empty group
      not rendered; translated title.

## 5. Text, translations, screening

- [x] 5.1 Group form saves title/description through `coerce_creator_html`; translation saver for
      `QuestionGroupTranslation`; `translation_gaps.py` counts group fields.
- [x] 5.2 `content_screening.collect_text()` includes group title/description (+ translations);
      live content saves call `_rescreen_if_live`.
- [x] 5.3 Tests: script stripped on save and import, gaps reported, screening sees group text.

## 6. Editor

- [x] 6.1 `editor_forms.QuestionGroupForm`; views `editor_group_create` (section / `?parent=`),
      `editor_group_edit` (autosave under `EDITOR_AUTOSAVE`, 422 JSON on errors),
      `editor_group_delete`, `editor_group_preview_live`; URLs. Structural vs content locks per D6.
- [x] 6.2 `editor/partials/group_form_modal.html`: Name, Description (Quill), Display as, Visibility
      (`_visibility_block.html` with host kind `group`), translations, questions inside,
      "Respondent sees" pane.
- [x] 6.3 `editor/partials/group_list_item.html`; section list and in-row sub-question lists render
      merged runs (`items` in context); "Add group" buttons next to "New Question" and
      "+ Add Sub-question"; badges (`visibility_info`, dependents, comments, `Group · N`, style).
- [x] 6.4 `editor_items_reorder` (nested payload, ownership check, 0..N renumber, sets/clears
      `Question.group`); `survey_detail.html` Sortable: shared group name per container, groups
      only in the top list, long-press on touch; section and sub-question lists use it.
- [x] 6.5 Existing create / sub-question create / duplicate / paste use `groups.next_order` /
      `shift_down`; duplicate keeps the group, paste lands ungrouped.
- [x] 6.6 Delete dialog: empty group → plain confirm; otherwise two choices, "only the group"
      (default) / "with its N questions" (`with_questions=1`, answer count beneath members,
      `_refuse_if_answers_at_risk`, the existing 409 acknowledgement UI); live survey: structural controls
      carry `data-gate`, content controls follow `is_read_only`.
- [x] 6.7 Tests `GroupEditorTest`: create in section and under a parent, edit autosave, delete only the group keeps
      members in place, delete with questions 409 without ack / deletes members + answers with ack,
      empty group deletes in one step, reorder in/out/whole-group, foreign ids 400, group into group refused,
      live survey: retitle in place + rescreen, create/rule change 403, preview renders unsaved
      style.

## 7. Serialization and lifecycle

- [x] 7.1 `serialization.py`: `groups` per section, `sub_question_groups` per parent, `group` per
      question; import creates groups first, remaps codes, drops unresolvable membership with a
      report line; `_apply_visibility_rules` group pass.
- [x] 7.2 `cloning.py`: `copy_section` and `clone_question` clone groups, re-point members, remap
      rules through the cloned code map; `group` in the decided fields.
- [x] 7.3 `versioning.py`: draft copy / restore keep codes and rules (via 7.2,
      `clone_top_level_questions`); `publish_draft` verified by test. `find_draft_field_loss` is
      NOT extended: it audits the hand-written field list of #329, and groups are copied through
      `plain_field_values`, so there is no list to drift.
- [x] 7.4 Tests: ZIP round trip (section + pop-up group, translations, rule), old archive imports,
      bad membership report line, duplicate section / point question remaps the group rule, draft
      add-group → publish keeps answers, restore version keeps groups.

## 8. Comments

- [x] 8.1 `comments.py`: `'group'` kind in `ANCHOR_KINDS`, `resolve_anchor`, `anchor_fields`,
      `open_counts`; badge on the group row and modal; deep link.
- [x] 8.2 Tests: thread on a group, count on the row, survives `publish_draft`.

## 9. Read surfaces and wrap-up

- [x] 9.1 Test: export of a grouped pop-up has the same columns as without the group.
- [x] 9.2 Changelog entry `survey/changelog/<date>-question-groups.html`; CLAUDE.md "Question
      groups" paragraph (model, continuous order, one partial, visibility host kind, reorder
      endpoint).
- [x] 9.3 Browser check (Playwright, dev server, 2026-10-19): editor list with section and pop-up
      groups; drag of a question into a pop-up group (stored order + membership, list re-rendered);
      group modal autosave + live preview; respondent pop-up hides "Your visit" until a type is
      picked and re-measures its height (found and fixed: Leaflet keeps the opening height, and
      `popup.update()` would wipe the form — layout-only re-measure now); collapsible section
      group opens itself on Finish with its required question empty. Not checked: long-press
      drag at 390 px (no touch emulation in this run). Full `survey` + `billing` suite once.
