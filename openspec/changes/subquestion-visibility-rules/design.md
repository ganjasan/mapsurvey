## Context

The section-level engine (`compute_visibility`) is one pass per session over the section chain:
sections and top-level questions, answers keyed by question code. A pop-up is different in one way
only: the same sub-questions are answered many times per session — once per placed feature
(`parent_answer_id`) or per layer object (`layer_object`). So a pop-up rule is evaluated per
feature with that feature's own answers, never against the session. Everything else (rule shape,
any-of, fail-open verdicts, the structural lock, the kill switch) is reused.

## Decisions

### D1. Controller scope: the same pop-up only

A sub-question rule names an earlier `choice`/`multichoice` **sibling** (same
`parent_question_id`, smaller `order_number`). Not a section question, not another pop-up. That is
what the issue asks for, it keeps evaluation purely local (one feature's properties are the whole
input), and it is what the editor can explain in one optgroup. A sub-question rule whose controller
is not a sibling is **broken** (fails open, badged) — the same verdict as a top-level rule pointing
forward.

### D2. One engine, a second entry point

`visibility.popup_visibility(parent, answers_by_code, enabled=None)` → `PopupVisibility` with
`question_visible {sub_id: bool}` and `broken {('subquestion', id): reason}`. It builds a
`questions_index` from `parent.subQuestions()` (section index 0, order = `order_number`) and reuses
`_rule_verdict` with the `'question'` positional check — so "earlier sibling" is literally the same
test as "earlier question in the section". `compute_visibility` is untouched: `_iter_questions` is
top-level only, and sub-question rules never reach it. `lint_rules` and `describe_rule` learn the
`'subquestion'` host kind; `controller_options` gets a sibling variant.

### D3. Respondent: keep the DOM, disable the hidden

The pop-up HTML (`subquestions_forms[code]`, rendered once per section) keeps every sub-question;
the client toggles `.question-card[data-field-name]` inside the pop-up `<form>` and disables the
inputs of hidden cards. Both pop-ups already serialise with `serializeArray()`, which skips
disabled inputs, so a hidden follow-up never enters `feature.properties` (geo) or `_objectAnswers`
(objects). The rules ride `#section-data[data-popup-visibility-rules]` as a flat
`{sub_code: {question_code, choice_codes}}` (codes are unique per survey); the hook is
`initPopupFields(root)`, which both pop-ups call after restoring values — one bind site, and the
restored state decides the initial visibility. Geo features keep `properties` across opens, so
Apply/close also **deletes** the properties of hidden cards (and their `-other` write-in); the
object path rebuilds its map from scratch and needs nothing.

Required: the pop-up has no required check of its own today (Apply is always allowed), and the
section-level required pass only looks at `#section_question_form`; hidden ⇒ never required holds
by construction. Nothing is trusted client-side: the server discards anyway.

### D4. Server: discard at write time == purge

The section POST deletes and re-inserts a session's answers for the section on every submit, and
sub-answers come from the posted properties / `obj__` fields. So filtering at insert time IS the
purge — there is no stored branch to clean afterwards and no cross-section case (the controller is
in the same pop-up). Geo: for each feature, `answers_by_code` = the choice-type properties
(`choice_ids`), `popup_visibility(question, …)`, skip hidden keys. Objects: same per object key in
`_save_object_answers`. Kill switch off ⇒ `popup_visibility` returns all-visible, the GET ships
`{}`, the block does not render.

### D5. Editor: same block, one group

`_visibility_block_context(survey, host_section, 'subquestion', host=…, parent=…)` returns one
group labelled "This pop-up" with the eligible siblings (all choice siblings for a new sub-question,
earlier ones for an existing). The template takes the group label from the object it is given
(`title` falls back to `name`), so a `SimpleNamespace(title=_('This pop-up'))` needs no template
branch. The modal already includes the block and `editor_subquestion_create` already parses the
posted rule — only the context was missing. `editor_question_edit` drops its `is_subquestion`
exclusions. Badges: `question_list_item.html` is recursive, so once `visibility_info` resolves the
kind from `parent_question_id_id` the section list is covered; the in-modal list gets the same two
badges. `visibility_dependents` already counts by code and needs no change. Structural lock:
`structural_question_changes` already names the visibility rule for any `Question`.

### D6. Serialization and duplication

Export already writes `visibility_rule` on sub-questions. Import: `_apply_visibility_rules` gains a
pass over `sub_questions` — controllers are the imported siblings of that parent (by remapped code)
— and drops an unresolvable rule with the same report line. Clone: `clone_question` clones
sub-questions with regenerated codes, so a copied rule would point at the source sibling; after the
loop it remaps `question_code` through the sibling code map (the pattern `copy_section` uses for
intra-section rules). Cross-survey paste KEEPS pop-up rules (the controller travels with the
parent). `publish_draft` and version restore clone with `regenerate_code=False` and keep the rule
verbatim. `check_draft_compatibility` is about orphaned answers and is untouched: a rule never
orphans an answer.

### D7. Read surfaces

Responses, export, `object_stats`, public results read sub-answers as rows; a hidden sub-question
simply has no row for that feature. No change, verified by the acceptance test on export columns.

## Risks

- A creator puts the controller AFTER its dependent by reordering sub-questions → broken, fails
  open, badged (D1). Same as today for top-level.
- The pop-up's write-in (`other_option.js`) syncs on `change` too; it runs after this module and
  reads `disabled` state, so a hidden choice card's write-in stays disabled.
