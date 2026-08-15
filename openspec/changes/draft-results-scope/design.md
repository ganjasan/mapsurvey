# Design

## Context

Two links tie a `SurveyHeader` to its relatives:

- `canonical_survey` — an **archived version** points at the canonical. This is the "family".
- `published_version` — a **draft copy** points at the canonical it will replace.

Every scope helper in `survey/versioning.py` reads the first link only. `canonical_of()` returns
`survey.canonical_survey or survey`, so for a draft it returns the draft, and `family_ids()`,
`family_headers()`, `lineage_map()` and `resolve_version_scope()` all inherit that. The docstring on
`family_ids` even states the exclusion as intent: drafts "never own real sessions". True — but they
own *test* sessions, and those are exactly what the creator ends up staring at instead of their data.

## Goals / Non-Goals

**Goals**

- A draft's Results reports the published family by default.
- Draft test sessions are reachable, but only when explicitly selected — never mixed into real data.
- Discarding a draft works whether or not it has been previewed.

**Non-Goals**

- Changing what `family_ids()` means. It stays "canonical + archived", because the public results
  page builds its clean-session set from it and must never publish test data.
- Moving or preserving draft test sessions at publish time. `publish_draft` already deletes them;
  this change makes discard agree with publish, not the other way round.
- The `Draft · v1` badge on the draft's header, which shows the draft's own default
  `version_number` rather than the version it would become. Misleading, but a separate cosmetic fix.

## Decisions

### 1. `canonical_of()` follows `published_version`

```python
return survey.canonical_survey or survey.published_version or survey
```

One line, and every derived helper becomes draft-aware at once: the version picker lists the
family's versions, the export resolves the family, and `lineage_map` groups against published
questions.

Considered and rejected: resolving the draft only inside the analytics views. It would have left
`editor_views._reserve_choice_codes` (`editor_views.py:55`) reading `family_ids(draft) == {draft}`,
so editing a choice list in a draft would not see which codes published answers already use — the
collision guard silently weakens exactly where drafts are edited. Fixing the shared helper fixes
that path too.

The draft itself is still not a family member: `family_ids()`/`family_headers()` query by
`canonical_survey`, which a draft never sets. So "All versions" stays free of test sessions.

### 2. `draft` is a value of the existing `version` filter

Rather than a separate toggle, the draft becomes one more option in the picker the creator already
uses. `resolve_version_scope(survey, 'draft')` returns a scope whose single header is the family's
draft copy; `VersionScope.is_family` is False for it, so the export writes unprefixed filenames as
it does for any single-version scope.

The option is offered whenever the family *has* a draft — including from the canonical's Results, so
a creator does not have to navigate into the draft to inspect a preview. `version_choices()`
therefore also has to render for a single-version survey with a draft, where it previously returned
an empty list (no filter at all).

Unresolvable values already fall back to the whole family (`_requested_version_number` returns
`None`), so `version=draft` on a family with no draft degrades to "All versions" rather than
erroring — the same rule `v99` follows.

### 3. Lineages absorb the draft only under the draft scope

A draft's questions are clones: same `code` and `input_type`, new ids. Under `version=draft` the
answers point at those new ids, so `lineage_map` must include the draft's header ids or every column
reports zero. It takes `include_draft=False` and `SurveyAnalyticsService` passes
`include_draft=(scope.value == 'draft')`.

`entry['current']` still comes from the canonical, so the columns and their order are the current
structure; a question that exists *only* in the draft appears after them, in the archived group. The
`vN–vM` range label ignores draft headers — a lineage seen only in the draft is labelled `draft`
rather than borrowing the draft's placeholder `version_number`.

### 4. Session actions get their own scope helper

`analytics_views` guards every session-level action with `survey_id__in=family_ids(...)`. Under the
draft filter a listed session would be un-openable, un-taggable and un-deletable. A new
`family_ids_with_draft(survey)` (family + draft copy) backs those lookups. The guard keeps its
purpose — a session id from another survey is still rejected — it just admits the draft's own.

`public_results.py` keeps plain `family_ids()`.

### 5. Discard mirrors publish

```python
with transaction.atomic():
    SurveySession.objects.filter(survey=survey).delete()
    survey.delete()
```

Answers cascade from the session. `SurveyEvent.session` is `SET_NULL`, so events survive
de-referenced — identical to what `publish_draft` leaves behind, and the funnel already tolerates it.

The audit entry is written before the delete (as today) and names the canonical, so the trail
survives the draft it describes.

## Risks / Trade-offs

- **`canonical_of` is on hot paths.** `survey.published_version` is a FK access, so a draft costs one
  extra query the first time per instance. Only draft copies pay it; canonical and archived headers
  short-circuit on the first `or`.
- **A creator may misread the Draft option as "results so far".** Mitigated by labelling it
  `Draft (test)` and by it never being the default.
- **Discard now destroys data.** Test sessions only, and publish already destroys the same rows —
  but a creator who previewed a draft with real intent loses those answers on discard. Accepted: a
  draft is not a collection surface, and the alternative (keeping orphan sessions) is what produces
  the 500.

## Migration Plan

None. No schema change; behaviour changes on deploy. Drafts stuck in prod become discardable
immediately, and their Results start reporting the family on the next page load.

## Open Questions

- Should the version picker's Draft option be hidden from collaborators with `viewer` role? Left
  visible for now — a viewer can already open the draft's Results.
