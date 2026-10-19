## Why

When twenty questions depend on one condition, the creator sets the same visibility rule twenty
times and the respondent sees them as one flat list. There is no way to give a run of questions a
shared title, a description and one rule — neither in a section nor in a geo pop-up. In the epic's
target picture ("one point question for many kinds of place", #343) the pop-up asks *Type of place*
first and then shows the shared follow-ups as blocks ("About this place", "Your visit") plus one
kind-specific block chosen by a rule; without groups each of those follow-ups carries its own copy
of the rule and the pop-up reads as an undifferentiated stack (issue #340).

## What Changes

- New model `QuestionGroup(section, parent_question?, code, title, description, display_style,
  visibility_rule, order_number)` and `Question.group` (nullable FK, `SET_NULL`). A group is a
  container, not a question type: it sits between a section and its questions, or between a geo /
  Objects-on-the-map question and its sub-questions. Groups never nest. Answers stay rows on the
  questions inside.
- **One continuous order**: a group's `order_number` lives in the same sequence as the questions of
  its section (or pop-up), and its members follow it contiguously. `section.questions()`,
  `subQuestions()` and the visibility engine's "controller is earlier" test keep working unchanged.
- `QuestionGroupTranslation(group, language, title, description)` — group text is translated like
  question text. The description is creator rich text and passes `coerce_creator_html`.
- **Visibility**: a group may carry one `visibility_rule` (same shape, same any-of / answered
  modes, same fail-open verdicts). A hidden group hides every question inside it (hidden ⇒ never
  required, answers discarded at POST and purged). A question inside may carry its own rule on top.
  Works in sections (per session) and in pop-ups (per feature / per object).
- **Display styles**: `plain` (title + description, questions in the flow), `card` (framed block),
  `collapsible` (title with a chevron, starts closed, opens on tap, opens by itself when a required
  question inside is unanswered on submit). Respondent sections, geo pop-ups, layer-object pop-ups,
  the editor's section preview and a "Respondent sees" pane in the group modal all render through
  the same partial.
- **Editor**: "Add group" next to "New Question" in a section and next to "+ Add Sub-question"
  under a geo question; a group row in the list (title, description line, `Group · N`, style badge,
  visibility badges, comment badge) with its own modal (Name, Description, Display as, Visibility,
  translations, the questions inside); SortableJS drag of questions in and out of a group and of the
  group as a whole (long-press on touch). Deleting a group asks: delete only the group (default —
  its questions move up one level in place) or the group with its questions (through the existing
  "N answers will be destroyed" acknowledgement).
- **Live surveys**: title, description, display style and translations are safe in-place edits
  (re-screened like other live creator text); adding, deleting, moving questions in/out, and the
  group's rule are structural and go to "Unpublished changes".
- ZIP export/import carries groups (additive, old archives import unchanged); duplication and draft
  copies clone groups; `publish_draft` moves them with their sections; comment threads can anchor to
  a group (`group:<code>`); content screening and translation gaps read group text. Data export
  keeps its columns (question order is unchanged by construction). AI generation ignores groups in v1.

Out of scope: repeating a group per item (Loop & Merge), reusing one group across questions
(#318 option 2), nested groups, AI-generated groups.

## Capabilities

### New Capabilities
- `question-groups`: the group container — model and ordering, display styles on every respondent
  surface, editor authoring (create, edit, reorder, drag in/out, delete), translations, live-edit
  classification, serialization, duplication and draft lifecycle, comment anchor, screening.

### Modified Capabilities
- `conditional-visibility`: a rule may sit on a group; a hidden group hides its members; group
  rules in pop-ups are evaluated per feature; controllers, lint, badges, import and cloning cover
  the group host.

## Impact

- `survey/models.py` + migration `0099` — `QuestionGroup`, `QuestionGroupTranslation`,
  `Question.group`, `CommentThread.group_code` + constraint branch.
- `survey/visibility.py` — group host kind in `compute_visibility`, `popup_visibility`,
  client rules, `lint_rules`, `describe_rule`, `controller_options`.
- `survey/forms.py`, `partials/question_fields.html`, new `partials/question_group.html`,
  `assets/js/conditional_visibility.js`, `base_survey_template.html` (required check, collapsible),
  respondent CSS.
- `survey/views.py` — section GET/POST (group rules shipped and enforced), pop-up HTML.
- `survey/editor_views.py`, `survey/urls.py`, `editor_forms.py`, new `editor/partials/group_list_item.html`
  and `group_form_modal.html`, `section_detail_form.html`, `question_list_item.html`,
  `survey_detail.html` (Sortable), reorder endpoint.
- `survey/serialization.py`, `survey/cloning.py`, `survey/versioning.py`, `survey/comments.py`,
  `survey/content_screening.py`, `survey/translation_gaps.py`.
- `survey/tests.py`, `survey/changelog/<date>-question-groups.html`, CLAUDE.md note.
