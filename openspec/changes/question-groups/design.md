## Context

Questions live in a section (`Question.survey_section`) or under a geo / Objects-on-the-map parent
(`parent_question_id`), ordered by `order_number` (nothing enforces uniqueness). Visibility rules
sit on sections, questions (#338: and sub-questions); `survey/visibility.py` is the one engine for
the respondent form, the POST discard/purge, navigation, progress and editor lint. The positional
test "controller is earlier" compares `(section index, order_number)`. Respondent markup is one
partial, `partials/question_fields.html`, which iterates the form's fields and emits one
`.question-card[data-field-name]` each; sections and both pop-ups render through it, and
`conditional_visibility.js` toggles cards by `data-field-name`. Editor lists are
`question_list_item.html` (recursive for sub-questions) with SortableJS POSTing ids in DOM order
to `editor_questions_reorder`. No mockup for the group card exists yet in either repo; the card
style is designed here (see D5).

Decided with the owner (2026-10-19): one continuous order (D2); group text is translated in v1 (D3).

## Goals / Non-Goals

**Goals:** a group gives a run of questions (section or pop-up) a title, a description, a display
style and one rule; one rendering path on every respondent surface; the editor can create, edit,
reorder, drag in/out and delete groups; every lifecycle path that copies or moves questions
(ZIP, duplicate, paste, draft, publish, restore) keeps groups intact.

**Non-Goals:** nested groups; repeating a group per item; one group shared by many parents (#318
option 2); AI-generated groups; groups in Responses / export / public results (they read answer
rows on questions, which do not change); a kill switch (owner rule: no new kill switches — the
feature is inert until a creator adds a group).

## Decisions

### D1. Model

```
QuestionGroup
  survey_section    FK SurveySection, CASCADE
  parent_question   FK Question, null, CASCADE      # set ⇒ a pop-up group
  code              CharField(50)                   # unique within the survey, like Question.code
  title             CharField(512, blank)
  description       TextField(blank)                # creator rich text
  display_style     plain | card | collapsible      (default card)
  visibility_rule   JSONField(null)                 # same shape as Question.visibility_rule
  order_number      IntegerField                    # same sequence as its siblings (D2)
QuestionGroupTranslation(group, language, title, description)   unique (group, language)
Question.group      FK QuestionGroup, null, SET_NULL, related_name='questions'
CommentThread.group_code  CharField(null) + a 'group' branch in commentthread_one_anchor_only
```

Invariants (enforced by the editor endpoints and the import, checked in `QuestionGroup.clean()` and
a test helper, not by DB constraints): a member's `survey_section` equals the group's and its
`parent_question_id` equals the group's `parent_question`; groups never contain groups (there is no
FK for it); a top-level group holds only top-level questions, a pop-up group only sub-questions of
its parent. `SET_NULL` on `Question.group` is what makes "delete only the group" true without code: members
stay where they are in the sequence, ungrouped. "Delete with questions" deletes the members
explicitly first (D6).

Alternative considered: a `group` input type (a Question row that "contains" the following ones).
Rejected — every reader of questions (forms, export, analytics, object_stats, public results, AI,
serialization) would have to learn to skip it, and its answers column would be empty everywhere.

### D2. One continuous order

A group's `order_number` is a slot in the same sequence as its sibling questions; its members
carry the next `order_number`s contiguously. So the "earlier" test needs no change for questions,
and a group rule is checked with the group's own `order_number` (a group's controller must be
before the group, hence before every member). Readers that walk `section.questions()` /
`subQuestions()` keep their order. Rendering needs the runs: `group_runs(questions, groups)` in a
new `survey/groups.py` merges both lists by `order_number` and returns
`[(group | None, [questions])]`; a member whose group is out of place (non-contiguous after a bad
import or an old reorder) closes the run, so a broken invariant degrades to "the group's header
appears twice", never to a lost question. The single writer of the sequence is the new reorder
endpoint (D7), which renumbers the whole list 0..N.

Alternative considered: a two-level order (slot + inner order). Rejected by the owner — every
order reader would have to sort by a pair.

### D3. Text and translations

`title` is plain text (escaped on render); `description` is creator rich text authored in Quill
like `Question.subtext`, stored through `coerce_creator_html` on every write path (group form, its
translation savers, ZIP import, the live preview). `get_translated_title(lang)` /
`get_translated_description(lang)` mirror the question helpers. `translation_gaps.py` counts group
title/description per language; `content_screening.collect_text()` includes them; the live saves go
through `_rescreen_if_live`.

### D4. Visibility

- Host kind `'group'`. Top-level group: `_rule_verdict(rule, 'question', s_idx, group.order_number,
  questions_index)` — exactly a question's check. Pop-up group: the sibling index of #338.
- `compute_visibility`: `group_visible[g.id] = section_shown and own(g)`; a member's verdict is
  `group_visible[g] and own(q)`. Cascade order: a hidden group's members are hidden, so a later
  question controlled by a member sees it as unanswered — the existing cascade, because members are
  in `questions_index` already.
- `popup_visibility(parent, answers)`: same, per feature / object; group verdicts in
  `PopupVisibility.group_visible`.
- `VisibilityMap.group_visible` feeds rendering. POST discard and purge need no new code: they act
  on `question_visible`, which already folds the group in.
- Client: `client_rule` dicts for groups are keyed `group:<code>` in the same
  `data-visibility-rules` / `data-popup-visibility-rules` maps; `applyRules` finds
  `.question-group[data-group-code]` for those keys, sets `hidden` and disables every input inside.
  A member's own card rule still applies inside a shown group.
- A group whose rule is controlled from an earlier section and is false is not rendered at all,
  same as a hidden question today (`_build_section_context` drops its members; `group_runs` drops a
  group with no rendered members).
- `lint_rules`, `describe_rule('group', …)`, `controller_options(..., 'group')`,
  `popup_controller_options` and `visibility_dependents` learn the kind; members of a group are
  not offered as controllers of their own group (they are after it).

### D5. Respondent rendering

`SurveySectionAnswerForm` keeps building fields in question order and additionally exposes
`form.field_runs` = `group_runs` mapped to bound fields. `question_fields.html` iterates runs: a
`None` run renders cards exactly as today; a group run includes `partials/question_group.html`:

```
<section class="question-group question-group--{style}" data-group-code="…">
  <header class="question-group__head">          ← <button aria-expanded> for collapsible
    <h3 class="question-group__title">…</h3>
    <div class="question-group__desc">…|safe</div>
  </header>
  <div class="question-group__body"> …member cards… </div>
</section>
```

`plain` = title + description with spacing, no frame; `card` = the question-card surface (border,
radius, padding) around the whole run with members as unframed rows inside, so it reads as one
block in a pop-up; `collapsible` = `card` with a chevron button, body collapsed by default
(`hidden` + `aria-expanded=false`), toggled on tap. The submit-time required check in
`base_survey_template.html` opens a collapsed group that holds an unanswered required card before
focusing it. Pop-ups get the same markup because their HTML is rendered from the same partial per
parent; `initPopupFields` binds the collapsible toggle. The editor section preview reuses the
respondent context and therefore the partial. CSS lives in the respondent stylesheet next to
`.question-card`, with the dark-mode tokens the card already uses. A static mockup of the three
styles (section + pop-up, light/dark) is produced as the first task and approved before templates
are written.

### D6. Editor authoring

- Endpoints (`survey/editor_views.py`, `urls.py`): `editor_group_create` (section or `?parent=`),
  `editor_group_edit`, `editor_group_delete`, `editor_group_preview_live`, `editor_items_reorder`.
  Create/delete/rule change/membership change call `_check_structural_edit_allowed`; title,
  description, style and translations call `_check_content_edit_allowed` and rescreen.
- Group modal (`editor/partials/group_form_modal.html`): Name, Description (Quill), Display as
  (three radio cards with a thumbnail), Visibility (the existing `_visibility_block.html` with host
  kind `group`), translations tab, list of the questions inside, and a "Respondent sees" pane that
  renders the unsaved group with its members through `editor_group_preview_live`. Autosave follows
  `EDITOR_AUTOSAVE` like the question edit form; create has an explicit Create button.
- Lists: `editor/partials/group_list_item.html` renders `<li class="question-item question-item--group"
  data-item="g:<id>">` with drag handle, title, a one-line description excerpt, `Group · N`, style
  badge, visibility badges (`visibility_info` resolves the group kind), comment badge, and a nested
  `<ul class="group-question-list">` of member `question_list_item`s. Section list and in-row
  sub-question lists both render the merged runs (the section view passes `items`).
- "Add group" next to "New Question" and next to "+ Add Sub-question" (one row on desktop,
  stacked on a phone); a new group lands at the end of the sequence. Each group row ends with
  "Add question to group": the create modal carries `?group=<id>` on every post and
  `groups.place_in_group` gives the question the slot after the group's last member (owner
  feedback 2026-10-21: creating outside and dragging in was the only way, and it was not
  acceptable). Drag remains the way to move existing questions in and out.
- "Respondent sees" (`group_preview_frame.html`) draws the group between two faded neighbour
  questions — pop-up styling for a pop-up group — and fills an empty group with two example
  questions, so plain / card / collapsible can be told apart before anything is in the group;
  a Tips card under it explains each style, the chosen one highlighted.
- Delete (decided with the owner 2026-10-19: ask, do not assume): a group with questions opens a
  small dialog with two radio choices — "Delete only the group — its N questions stay in the
  section" (pop-up: "…stay in the pop-up"), the default, and "Delete the group and its N
  questions". The POST carries `with_questions=1` for the second. That path counts answers
  beneath the members (the helper `editor_question_delete` uses, summed) and calls
  `_refuse_if_answers_at_risk`, so the existing 409 → "N answers will be destroyed" acknowledgement
  flow of `warn-before-destroying-answers` applies unchanged; then it deletes members and group in
  one transaction. "Only the group" destroys no answer and needs no acknowledgement. An empty group
  gets the plain one-line confirmation. Both are structural (live survey → "Unpublished changes").

### D7. Reorder and drag

One endpoint, `editor_items_reorder`, takes the nested DOM state of ONE list:
`[{"g": 3, "q": [12, 13]}, {"q": 14}, …]`, validates that every id belongs to that section/parent
(the old endpoint did not check — this one does, and refuses mixed sections/parents with 400),
renumbers `order_number` 0..N across groups and questions, and sets/clears `Question.group` from
the nesting. SortableJS: the top list and every `.group-question-list` share a Sortable `group`
name per container (section list ↔ its groups; a pop-up list ↔ its groups — never across), groups
themselves can only be dropped in the top list (`put` filter on `.question-item--group`), touch
uses `delay:300 + delayOnTouchOnly` as elsewhere. Any change in nesting is structural; on a live
survey the list is locked as today (`STRUCTURE_LOCKED`). `editor_questions_reorder` stays for
callers that only reorder flat lists, but section and sub-question lists move to the new endpoint.

Create/duplicate/paste paths that compute `Max(order_number)+1` or shift order keep working on the
continuous sequence by including groups in the max/shift (`groups.next_order(section, parent)`,
`groups.shift_down(...)`). A duplicated grouped question stays in its group, right after the
source; a pasted question lands ungrouped.

### D7b. Moving a question between the section and a pop-up (owner request 2026-10-21)

All question lists of one section share ONE Sortable group, so a row can be dropped from the
section into a pop-up (its list or a group in it) and back. Same-root drops keep using
`editor_items_reorder`; a cross-root drop calls `editor_question_move` with the question, the
target root (`section_id`, `parent_id`) and the target root's nested state. The server:
refuses `SUBQUESTION_DISALLOWED_INPUT_TYPES` into a pop-up and a question that owns
sub-questions (400); counts answers beneath the question and goes through
`_refuse_if_answers_at_risk` (answers are per respondent in a section and per mark in a pop-up,
so they cannot be carried over — they are deleted); re-parents, clears `group`, resets
`share_with_respondents` outside an Objects pop-up; removes the moved question's rule and every
rule naming it whose controller would no longer come earlier in the same scope (reported back as
`removed_rules` and shown in a dialog); then renumbers the target root from the posted state.
Groups do not cross roots (a group row is accepted only by its own root). The client refuses
the disallowed types before posting (`data-input-type`), the server is the check.

### D8. Serialization, cloning, lifecycle

- ZIP: each section gains `"groups": [{code, title, description, display_style, visibility_rule,
  order_number, translations}]`; each question with sub-questions gains `"sub_question_groups"`; a
  question names its group by `"group": "<code>"`. Additive, `FORMAT_VERSION` stays `1.0`; an
  archive without the keys imports with no groups. Import creates groups before questions, remaps
  colliding codes (`code_remap`), drops a `group` reference that resolves to nothing (report line),
  and `_apply_visibility_rules` gains a group pass (top-level pool / sibling pool).
- Cloning: `copy_section` clones its top-level groups and `clone_question` its pop-up groups
  (code regenerated when the caller regenerates codes, rule kept under the same `keep_rule` rule and
  remapped through the cloned code map), and members are re-pointed at the clones. `group` is not a
  plain field, so it is added to the decided-fields list with explicit handling.
- `clone_survey_for_draft` / `editor_restore_version` go through the same helpers with
  `regenerate_code=False`, so groups keep codes and rules. `publish_draft` moves sections with
  `.update()`; groups FK to the section and move with it. `check_draft_compatibility` is about
  orphaned answers and is untouched; `structural_section_changes` is unchanged — group structure
  changes are refused on the live survey by the endpoints themselves (D6).
- `find_draft_field_loss` gains the group fields so the audit command keeps meaning "nothing lost".

### D9. Comments

`ANCHOR_KINDS` gains `'group'`; the anchor key is the group `code` (stable across
`publish_draft`, like question anchors); `resolve_anchor`, `anchor_fields`, `open_counts`,
`thread_counts` handle it; the group row and the group modal carry the badge.

### D10. What does not change

Answers, export columns (question order is unchanged by D2), Responses, analytics, object_stats,
public results, AI schema/materialisation (it writes no groups; a generated survey has none).

## Risks / Trade-offs

- [Non-contiguous members after an edge-case write] → `group_runs` degrades without losing a
  question (D2); the reorder endpoint renumbers and fixes it on the next drag; a test covers the
  degraded render.
- [Two Sortable nesting levels on touch are fiddly] → only one container family per list, groups
  cannot be dropped into groups; verified in a browser at phone width.
- [`display_style` name collides with `Question.display_style`] → different models, different
  choices; the group form never reuses question widgets.
- [Old reorder endpoint has no ownership check] → the new one validates; the old one is left as is
  (out of scope), noted for follow-up.
- [A creator picks "with questions" by mistake] → "only the group" is the default and answers sit
  behind the 409 acknowledgement; questions without answers are gone, the same as deleting a
  question today.
- [Collapsible hides a required question] → submit opens the group before focusing (D5).

## Migration Plan

Migration `0099` adds two tables, one nullable FK and one nullable column + a replaced
CheckConstraint — additive, safe for the ~70 s overlap with the old instance (the old code never
reads the new columns; the constraint still admits every existing row). Rollback = revert the
code; the columns stay empty.

## Open Questions

- Visual of the `card` / `collapsible` styles — settled by the mockup task before templates.
