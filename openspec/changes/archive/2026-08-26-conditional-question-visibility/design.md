# Design — conditional visibility

## Context

Creators cannot express "show X only when Y = Z"; they write conditions into question
text and collect contradictory data (see `proposal.md`, `research.md`,
`conditional-visibility.mockup.html`). The design adopts the industry-consensus model:
declarative visibility rules on questions AND sections, one mechanism, no jump targets.

Relevant current-state facts (verified in code):

- `Question.choices` is a **JSONField**: `[{"code": <int>, "name": <str|dict>}, …]`.
  There is no per-option DB row to FK against. Questions carry a random string `code`
  (`question_code_generator`), remapped on ZIP import (`code_remap` in
  `serialization.py`).
- Sections are a linked list (`next_section`/`prev_section` FKs, `is_head`); progress
  is computed by walking it (`survey/views.py` ~line 935).
- The section POST handler (`survey_section`, `views.py` ~947) **deletes all of this
  section's answers for the session and rewrites them from POST**. The form is built
  with `initial=request.POST` and never validated (known bug, backlog
  `bug-answers-never-validated-server-side`) — required is client-side only.
- Answer prepopulation already loads a session's stored answers when re-entering a
  section, so cross-section answer state is available server-side at render time.
- Geo sub-questions use `parent_question_id`/`parent_answer_id` and render inside the
  feature popup; their answers ride in GeoJSON `properties`.

## Goals / Non-Goals

**Goals:**

- One rule shape — *controlling question (`choice`/`multichoice`, earlier in survey
  order) + any-of set of its option codes* — attachable to a question or a section.
- Server-enforced not-applicable contract: hidden ⇒ never required, submitted/stored
  answers discarded.
- Cascade; fail-open on broken rules; editor badges + lint; rules survive
  duplicate/export/import; visible-chain navigation and progress.
- Env-var kill switch: respondent-side evaluation can be turned off (rules become
  inert, everything visible) without a deploy rollback.

**Non-Goals:**

- Jump targets, compound multi-question conditions, non-choice condition sources,
  "hide but keep answer" option, FD-14 map-context switching (see proposal Out of
  scope). Fixing the general server-side-validation bug (separate backlog item; this
  change's contract must not depend on it).

## Decisions

### D1 — Storage: one nullable JSONField on each host, referencing codes

`Question.visibility_rule` and `SurveySection.visibility_rule`, both
`JSONField(null=True)`:

```json
{"question_code": "q_ab12cd", "choice_codes": [1, 3]}
```

`null` = always visible. References are by **question `code`** and **choice `code`**.

- *Why codes, not FKs*: option identity only exists as a JSON code — there is nothing
  to FK to. Question `code` (not `id`) survives ZIP export/import via the existing
  `code_remap` machinery and copy/duplicate flows, exactly like geo sub-question
  property keys already do.
- *Why not reuse `parent_question_id`*: that relation means "renders inside the geo
  feature popup, answer becomes a GeoJSON property". Overloading it would break form
  building, popup rendering and export. Rejected.
- *Why not a Rule model/M2M*: v1 is exactly one rule per item; a table adds joins and
  migration surface for no expressive gain. The JSON shape can grow
  (`{"all_of": […]}`) later without schema change.

### D2 — Evaluation: one pure module, `survey/visibility.py`

```python
compute_visibility(survey, answers_by_question_code) -> VisibilityMap
  # VisibilityMap: {question_id: bool}, {section_id: bool}, visible_sections: [section]
```

Pure function of survey structure + a session's answers. Single pass in survey order
(sections along the linked list, questions by `order_number`):

- Section visible ⇔ no rule, OR rule satisfied. Question visible ⇔ its section
  visible AND (no rule OR rule satisfied) — the LimeSurvey/ODK AND semantics.
- Rule satisfied ⇔ controlling question is *itself visible* (cascade) AND the stored
  answer's `selected_choices` intersects `choice_codes` (any-of; works for `choice`
  and `multichoice` identically since both store a list).
- **Broken rule** (controller code not found, controller is not a choice type,
  controller not earlier in order, every referenced choice code gone) ⇒ **visible**
  (fail-open) — same verdict the editor lint reports. Partial breakage (some codes
  gone) keeps the remaining codes.
- Everything callers need derives from the map: `visible_sections` chain for
  navigation, per-section visible questions for forms, progress indices.

Used by: respondent GET (render), respondent POST (discard + navigation), editor
preview, editor lint, and later analytics (not-applicable is recomputable — rules are
pure functions of recorded answers, so no per-question display state is stored;
confirmed viable since answers are the only rule input).

### D3 — Server-side discard: in the POST save loop, plus branch garbage collection

The existing POST handler already deletes + rewrites the section's answers. Two
additions, neither dependent on form validation:

1. While saving, skip any question invisible under the **submitted** state (evaluate
   against POST values merged over stored answers). Its posted value is dropped —
   tampering, stale DOM and the back-button leak all die here.
2. After saving, delete this session's answers for questions that are now invisible
   under the new answer state — across ALL sections, not just the current one. This
   is the abandoned-branch cleanup (UJ-6: switch Area 7 → Area 4). One query over the
   session's answers joined to the visibility map; sessions are small (≤ hundreds of
   answers).

Deleting parent geo answers cascades to sub-answers (`parent_answer_id` CASCADE),
which is the correct fate for popup properties of a discarded feature.

### D4 — Navigation and progress: walk the visible chain

Replace the raw `prev_section`/`next_section` hops and the progress walk in
`survey_section` with the visible-chain from D2:

- `next` after POST = next visible section (evaluated on the just-saved answers);
  `back` = previous visible section. The stored linked list stays untouched — skipping
  is a read-time filter, exactly like `hidden_layers` stale-ID handling.
- `section_current/section_total` = indices within the visible chain. They may shrink
  or grow when a controlling answer changes; accepted (every platform shares this).
- Section rules may only reference questions from **earlier sections** (a section
  cannot depend on itself); question rules may reference same-section-or-earlier.
  Enforced by the editor picker and re-checked by the fail-open rule in D2.

### D5 — Respondent client: rules JSON in the partial, toggle + disable

The section partial embeds `data-visibility-rules` (rules of this section's questions
whose controllers are in the same section). A small JS module (new
`survey/assets/js/conditional_visibility.js`, included from the survey shell):

- On change of a controlling input, re-evaluates same-section rules, toggles the
  question card (`hidden` attribute + the soft reveal), and **disables** hidden
  inputs so they never post.
- Updates the client-side required-summary to count visible questions only.
- Cross-section effects need no JS: they materialise at the next server render (D4).
  This keeps the client dumb and the server authoritative (D3 catches anything the
  client missed).

### D6 — Editor: one shared Visibility partial, badges, lint

- New partial `editor/partials/_visibility_block.html` (controlling-question select +
  option checkboxes, mockup screen A/B), included by `question_form_modal.html` and
  `section_detail_form.html`; saved in the existing `editor_question_*` /
  `editor_section_detail` POST paths (autosave-compatible; the block posts
  `visibility_mode`, `visibility_question`, `visibility_choices`).
- The picker lists only `choice`/`multichoice` questions earlier in survey order
  (sections walked via the linked list), grouped by section title.
- Badges in `question_list_item.html` / `section_list_item.html`: condition summary
  chip, dependents-count on controllers, warning state for broken rules (computed by
  a lint helper in `visibility.py` reusing the same brokenness definition as D2).
  Uncovered-option lint renders under the section list (mockup screen C).
- Duplicate flows (`editor_question_duplicate`, `editor_section_duplicate`, copy/
  paste) copy `visibility_rule` verbatim — codes are survey-scoped and duplication
  stays within the survey, so references hold. Cross-survey paste drops the rule
  (controller doesn't exist there) with the standard broken-rule surfacing if kept.
- **Fan-out helper is cut from v1** (mockup keeps it as a future affordance);
  duplicate-carries-rule covers the Olney journey at acceptable cost.
- Live preview renders through the same partial pipeline, so D5 works there; the
  preview POST path already avoids persisting.

### D7 — Serialization: export verbatim, import remap, drop-and-report

- `_serialize_question`/section serializers add `visibility_rule`.
- Import: `question_code` passes through the existing `code_remap`; choice codes are
  preserved by import (codes are kept stable). A rule whose controller/choices can't
  be resolved is **dropped with a line in the import report** (never a silent
  half-rule). AI generation writes through the same import path and gets rules for
  free later.

### D8 — Kill switch

`CONDITIONAL_VISIBILITY` env var (default `True`, same pattern as
`MOBILE_EDITOR_NAV`). Off ⇒ D2 returns all-visible (rules inert respondent-side) and
the editor hides the Visibility block. Merge-to-prod-in-minutes safety per project
convention.

## Risks / Trade-offs

- [Visibility recomputed per request] → single structure walk + one answers query per
  session; both already happen in `_build_section_context`. No caching in v1.
- [Migration number collision with parallel worktrees] → check `django_migrations`
  leaves before merge (standing project rule); the migration is two nullable JSON
  columns, trivially reorderable.
- [Silent discard of abandoned-branch answers may surprise respondents] → matches all
  researched platforms; a confirm dialog is possible polish, out of v1.
- [Same-section controller answered *after* dependent in DOM order] → picker restricts
  to earlier `order_number`, so the dependent always sits below its controller.
- [HTMX partial swap re-init] → JS module initializes idempotently from
  `data-visibility-rules` on every swap (same pattern as existing section JS).
- [Editor allows deleting a controller with dependents] → allowed (fail-open + badge),
  because blocking deletion would leash unrelated editing; lint makes it visible.
- [`initial=request.POST` bug means required-hidden interplay is client-only today] →
  D3 does not touch required at all; when the validation bug is fixed separately, its
  fix must consult the visibility map — noted in that backlog item, not solved here.

## Migration Plan

1. Migration: add `visibility_rule` to `Question` and `SurveySection` (nullable JSON,
   no data migration — null = current behaviour).
2. Ship engine + respondent enforcement + editor UI together behind
   `CONDITIONAL_VISIBILITY`.
3. Rollback: set the env var to `False` (rules stay stored, become inert). Schema
   rollback never needed.

## Resolved Questions (owner decisions, 2026-08-26)

- **Progress label**: bare `2 / 3` — the numbers silently reflect the visible chain,
  no "for you" hint (matches every researched platform; avoids translating a hint
  into 75 content languages). The mockup's hint is dropped.
- **Rules on a published survey**: **draft-copy only**. The Visibility block follows
  the editor's existing `is_read_only` gating exactly like every other structure
  control — on a published survey it is read-only with the standard "Create a draft
  to edit" affordance, and rules reach respondents by publishing a new version.
  In-flight sessions stay pinned to their version (existing version routing), new
  sessions get the new version's rules. No extra warning UI is needed — the draft
  step *is* the warning. Sodankylä can still fix their live survey before 27.09 via
  draft → publish.
