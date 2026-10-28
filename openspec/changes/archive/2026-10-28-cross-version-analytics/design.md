# Design — cross-version-analytics

## Context

`publish_draft()` (survey/versioning.py:208) atomically: creates an archived
`SurveyHeader` (status `closed`, `canonical_survey` FK → canonical), FK-moves the old
sections (with their original `Question` objects and all `Answer` FKs intact) and all
`SurveySession`s onto it, then FK-moves the draft's sections (cloned questions, **new
ids, same `code`s**) onto the canonical, bumps `version_number`, deletes the draft.

Consequences that drive this design:

- **Question identity across versions is `code`, not `id`.** `check_draft_compatibility`
  already keys on `code`; publish preserves codes through cloning.
- **Old wording is preserved** — a v2 session's answers point at the v2 question objects,
  so session detail shows the original label even after a "typo fix" publish. This is a
  feature of clone+move; keep it.
- `PublicResultsService` already computes family-wide session sets
  (`_collect_survey_ids` = canonical + `canonical_survey` FK children) — the pattern to
  extract and reuse. Its per-block `_answers()` does NOT (single question FK) — a latent
  bug this change fixes.

## Decisions

### 1. One family helper, used everywhere
`family_ids(survey)` → canonical id + all version-copy ids (excluding live draft
copies, which never own sessions); `family_sessions(survey, include_deleted=False)`;
`lineage_map(canonical)` → `{(code, input_type): {questions: [per version], current:
Question|None, versions: "v1–v3"}}`. Lives next to the existing versioning helpers.
Public results' `_collect_survey_ids` is refactored onto it. Any future surface that
counts responses MUST go through it — scattered `filter(survey=...)` is the root cause
of this whole bug class.

### 2. Lineage key = `(code, input_type)`
`code` groups versions of "the same question"; including `input_type` in the key makes a
type change break the lineage automatically (a `choice` Q5 and its `text` v1–v2
predecessor report as two lineages). No mapping tables, no migrations: lineage is
computed at read time from the family's questions. Display disambiguation uses the
version range ("Q5 · text · v1–v2").

### 3. All-versions is the default read scope; version filter for clean cuts
`AnalyticsService(survey, version='all')`: `'all'` → family sessions; `'vN'` → that
version's survey id only; mirrors the export's existing `?version=latest|vN|all`
contract. The Results UI gets the same three-way filter; the sessions table shows a
version chip per row. Filters/selection (FilterManager/SelectionManager) operate on
session ids and flow through unchanged once `base_qs` is family-wide.

### 4. Presentation: canonical structure first, archived lineages appended
The canonical version defines question order and choice display. Lineages with no
current question render in an **"Archived questions"** group at the end, labeled with
their version range. Choice buckets are the union of current choices and historically
answered codes; codes absent from the current choice set are flagged "no longer
offered" (they render greyed, never silently merged or dropped).

### 5. Public results blocks resolve by lineage at read time
Keep the `question` FK (it anchors the block and survives in both directions), but
`_answers()` filters `question__code=block.question.code,
question__input_type=block.question.input_type,
question__survey_section__survey_header_id__in=family_ids`. Works whether the FK points
at an archived or a current question object. k-anonymity is unaffected (already
session-family-wide; lineage merge only grows buckets).

### 6. Prevent silent choice-code reuse at the editor
The one conflict read-time logic cannot detect: code 2 meaning "Bus" in v2 and "Train"
in v3 would merge silently. Guard at write time: when adding a choice, allocate
`max(current codes ∪ codes present in family answers) + 1`; reject manual assignment of
a code that historic answers use with a different meaning (different name at save time).
Question-code reuse is already mitigated (`_create_question` generates unique codes);
add the same family-wide check to manual code edits.

### 7. Sessions are never double-counted
Each session FK-points at exactly one version header, so family aggregation is a plain
union. Completion is the session's own `survey_complete` event — v2 completions counted
under v2's rules; no retro-validation against v3 requirements (linting already evaluates
answers against their own version's question objects — add a regression test, not code).

## What else was audited (and what we deliberately skip)

- **Performance tab** (traffic sources, completion by source, time-on-section): family
  scope via the same helper; time-on-section merges by section *name* (clones keep
  names).
- **Geo layers / heatmaps**: layers built per lineage, so archived geo questions'
  features still render; a broken lineage (point→polygon) yields two layers.
- **Sub-questions**: lineage applies to them identically (code-scoped); geo point labels
  on public maps already resolve sub-answers via `question__code__in` — family scope
  fixes them together with `_answers()`.
- **Export**: `?version=` already exists; add a `survey_version` column to the CSV so
  All-versions exports are self-describing. Column set = current questions + archived
  lineages (suffixed with their version range).
- **Trash view**: family-wide, same helper.
- **Delete survey**: must delete sessions of ALL versions (PROTECT), then version
  headers, then the canonical — verify the existing flow and cover with a test.
- **In-flight respondents during publish**: sessions are moved to the archived header
  while the respondent keeps POSTing to the canonical slug. Out of scope here (existing
  behavior), but flagged as an open question below.
- **Funnel/platform metrics**: not survey-scoped; untouched.
- **Wording drift**: none — see Context; compatible edits do not rewrite history.

## Risks / Trade-offs

- Lineage-by-code trusts creators not to repurpose a question's meaning while keeping
  its code and type. Accepted: the compat check already warns on structural breaks, and
  prose-meaning changes are undetectable by any scheme.
- All-versions table columns grow with archived lineages; mitigated by the version
  filter and by grouping archived columns last.
- Slight query cost for family unions; family sizes are tiny (versions per survey ≈
  1–5).

## Migration

None — no schema changes; lineage is computed at read time.

## Open Questions

- In-flight sessions during publish write answers against the *new* question objects
  while the session row was moved to the archived header (mixed-version session).
  Lineage aggregation absorbs the answers correctly, but the session's version chip may
  mislead. Investigate separately.
- Should the version filter also offer per-version *comparison* (v2 vs v3 side by side)?
  Deferred — nice-to-have on top of the lineage machinery.
