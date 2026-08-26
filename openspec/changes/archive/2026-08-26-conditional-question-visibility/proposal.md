## Why

Survey creators cannot express "show question X only if question Y was answered Z", so they
write the condition into the question text by hand ("SI HABITANT DU 8E SEULEMENT…",
"Mikäli toimit matkailualan yrittäjänä…") and every respondent sees every question. Two
confirmed institutional cases show the cost is data integrity, not just UX: in Sodankylä's
light-pollution survey (LOISTAVA, live until 2026-09-27) the follow-up "what bothers you
most about obtrusive light" was answered 4 times against only 3 respondents who said they
had noticed any — the contradiction feeds a municipal light-management plan. In Lyon's
transit survey, a question meant for ~16 respondents was shown to all 98. Backlog #12,
priority very high, oldest open feature request (2026-03-30).

## What Changes

Competitive research (see `research.md`) shows the industry consensus is **declarative
visibility at both question and section level, as one mechanism** (LimeSurvey and
ODK/XLSForm AND group-level and question-level relevance; Google Forms' only branching
primitive is section-level, so sections are the mass-market mental model). Platforms that
offer both visibility and imperative skip-jumps steer authors away from jumps. We adopt
the visibility model — no "go to" targets, ever.

- A creator can attach a visibility rule to **a question or a whole section**: *show this
  question/section only when a previous `choice`/`multichoice` question's answer matches
  one or more selected options*. One rule shape, one evaluation engine for both levels.
- A section whose rule is false is **skipped by next/prev navigation** while walking the
  existing `next_section_id` linked list. No stored jump targets — Back keeps working,
  loops are impossible by construction (Sodankylä's nine-neighbourhood grid: "Missä
  asut?" = "Asun muualla" hides the whole rating section).
- The respondent form hides/shows dependent questions live (client-side) as the controlling
  answer changes within the same section; cross-section effects apply on navigation.
- Server-side, a hidden question or section is treated as not applicable: it is never
  `required`, and an answer submitted for it (stale DOM, back-navigation after changing
  the controlling answer, tampering) is discarded — the Sodankylä contradiction and the
  Google-Forms back-button leak become impossible to record.
- **Cascade**: if the controlling question is itself hidden, its dependents are hidden
  too (industry-universal; prevents authors restating upstream conditions).
- Editor UI: on the question form and on the section, pick a controlling question
  (earlier in survey order, `choice`/`multichoice` only) and the triggering option(s).
  Conditioned items carry a **branch badge** in the structure pane (a fan-out of ten
  zone sections is illegible without it); the controlling question shows how many rules
  depend on it. Live preview respects rules so the creator can play both branches.
- **Duplicate carries the rule** (section and question duplicate) — the Olney fan-out
  (one zone choice → ten zone sections) is built by duplicating one conditioned section
  and re-ticking one checkbox per copy. An optional fan-out helper ("create one section
  like this per remaining answer") is a design decision, cuttable from v1.
- Rules survive ZIP export/import and survey versioning; edits that orphan a rule
  (controlling question deleted, option removed, question reordered past its dependent)
  are surfaced in the editor, not silently broken (MS Forms' reorder-breakage class).
  A broken rule **fails open** — the item is shown to everyone and badged as broken
  (silently hiding content is worse than showing it). The editor also lints options of
  a fanned-out controlling question that no section rule covers; a respondent whose
  answer matches no rule simply flows past the fan (visibility semantics make "no
  match" safe where jump semantics would dead-end).
- Progress (`section_current / section_total`) and the required-summary count the
  **visible chain for this session**, recomputed when a controlling answer changes —
  the documented failure of every navigation-based platform.
- Analytics/export mark not-applicable as distinct from unanswered. Because rules are
  pure functions of recorded answers, displayed-ness is computable after the fact — no
  per-question display state needs storing (design.md must confirm this holds).

**Out of scope** (deliberately):
- Imperative skip/jump targets ("after this question go to X") — visibility subsumes
  them without their loop/ordering failure modes.
- Map-context switching driven by answers (FD-14) — research confirms no competitor
  productizes it; it is a differentiator to build separately in the
  field-data-collection epic, not parity work to rush here.
- Conditions on non-choice answers (number ranges, text matching, geo predicates).
- Compound conditions (AND/OR across multiple controlling questions) — one controlling
  question, one-or-more triggering options (any-of) is the v1 rule shape; this is the
  documented floor of every mainstream platform.
- Survey123-style per-rule "hide but still submit" option — v1 always discards hidden
  answers (the research-tool consensus); the option is a possible future.

## Capabilities

### New Capabilities
- `conditional-visibility`: the visibility-rule model (controlling question + triggering
  options, attachable to a question or a section), cascade semantics, editor authoring
  UI, live respondent show/hide, and the server-side not-applicable contract (never
  required, submitted answers discarded).

### Modified Capabilities
- `survey-serialization`: ZIP export/import carries visibility rules; import resolves the
  controlling-question reference by position/identity within the archive.
- `survey-progress`: question counts and required-question accounting exclude questions
  and sections hidden for this respondent (a session must be completable when hidden
  questions are never answered; progress display must not over-count — the documented
  failure of every navigation-based platform).
- `respondent-session-routing`: next/prev section navigation skips sections whose
  visibility rule evaluates false for this session, in both directions.

## Impact

- **Models**: new rule storage on `Question` AND `SurveySection` (FK to controlling
  question + selected `OptionChoice`s, or a JSON rule field — design decision).
  Migration required; existing surveys unaffected (no rule = always visible). Note:
  `parent_question_id`/`parent_answer_id` already exist for geo sub-questions — design
  must decide reuse vs a parallel mechanism without breaking the sub-question flow.
- **Navigation**: the section next/prev walk (`respondent-session-routing`) gains
  rule evaluation; a session's visible-section chain depends on its answers.
- **Respondent form**: `SurveySectionAnswerForm` (survey/forms.py) and the section
  template — client JS for live show/hide; POST handler for the not-applicable contract.
  Known trap: the section POST handler currently never validates the form
  (`initial=request.POST`, backlog bug "answers never validated server-side") — this
  change's server-side contract must not silently depend on a fix that isn't there;
  design must state the interaction explicitly.
- **Editor**: question form modal + `editor_views.py` save path; live preview must respect
  rules.
- **Serialization**: `survey/serialization.py` (export, import, AI generation path).
- **Versioning/live surveys**: rules on a published survey follow the existing
  draft-copy path (owner decision 2026-08-26): the Visibility block is read-only on a
  published survey, changes ship by publishing a new version; in-flight sessions keep
  their version's rules, collected answers are never touched. Sodankylä (live until
  2026-09-27) fixes their survey via draft → publish.
- **Analytics/export**: CSV/GeoJSON export and the responses table gain a
  not-applicable distinction (minimal in v1: nothing breaks, empty cells stay empty).
