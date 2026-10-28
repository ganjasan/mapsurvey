## Context

`publish_draft()` moves the previous structure *and its sessions* onto an archived `SurveyHeader`,
so "which versions am I looking at?" is a question every creator-facing read has to answer.
`survey/versioning.py` already owns the family primitives (`canonical_of`, `family_ids`,
`family_sessions`, `lineage_map`) and its module comment already states the rule: *every
creator-facing count/aggregate must go through these helpers*. The `version` request parameter is
the one part of that rule that was implemented twice, once per surface, and drifted.

Two shapes are needed from a resolution:

- Analytics wants **ids**, to filter `SurveySession.survey_id__in` and
  `question__survey_section__survey_header_id__in`.
- The export wants **header objects, in order, with filename prefixes**, because it walks each
  version's questions and writes one file set per version.

That difference is why there are two functions. It does not justify two parsers.

## Goals / Non-Goals

**Goals**

- One parse of `version`, one fallback rule, one meaning for `latest`, shared by both surfaces.
- Both shapes (ids, ordered headers) derived from that single resolution.
- The default is deliberate and stated once, not implied by each caller's `GET.get` default.

**Non-Goals**

- Changing which sessions are clean (`is_deleted` / `validation_status`) or the `include_all=1`
  behaviour.
- A UI redesign of either version picker. The dashboard's Download button gets the scope appended;
  nothing else moves.
- Rejecting bad input with a 4xx. These are links a creator can bookmark and a version can be
  deleted underneath them; falling back to the default is friendlier than an error page, and once
  both surfaces fall back the same way the bug is gone either way.

## Decisions

### 1. The resolver lives in `versioning.py` and returns a scope object

`resolve_version_scope(survey, version) -> VersionScope`, a small frozen dataclass:

```python
VersionScope(
    value:    str,             # normalised: 'all' | 'vN'
    headers:  list[SurveyHeader],  # canonical first, then archived newest-first
    ids:      set[int],
    is_family: bool,           # len(headers) > 1
)
```

*Rationale.* `analytics.py` importing from `versioning.py` is the existing direction of dependency
(it already imports `canonical_of`, `family_ids`, `lineage_map`); `views.py` importing from it adds
no cycle. Putting the resolver in `analytics.py` and importing that into `views.py` would drag the
whole analytics service layer into the export path.

`analytics.py` keeps a `resolve_version_scope` name as a thin re-export returning `.ids`, so the two
existing call sites (`analytics.py:137`, `analytics.py:1418`) and their `self.scope_ids` contract
are untouched.

### 2. Normalisation, in order

1. Falsy (`None`, `''`) → the default.
2. `'all'` → the family.
3. `'latest'` → `canonical.version_number` — an alias, resolved before the numeric parse rather
   than crashing inside it.
4. `'vN'` / `'N'` → that version, if a header with that number exists in the family.
5. Anything else, including a well-formed number for a version that does not exist → the default.

*Rationale for `latest` as an alias rather than its own scope value:* the export's dropdown already
links `?version=latest` and those links are in the wild; the analytics picker emits `v3`. Resolving
`latest` to `vN` up front means one canonical form (`value` is always `all` or `vN`) with no third
case for the UI to display.

### 3. The default is `all`

Both surfaces default to the whole family, which is what analytics does today.

*Rationale.* The complaint the bug generates is "the export is broken" — the export is the surface
that disagrees with what the creator just read. Making the export match the screen resolves it in
the direction the creator already believes. "All versions" is also the honest answer to *how many
responses does this survey have*, which is the question asked when no filter is stated.

*Consequence, handled below:* the export's default changes behaviour for multi-version surveys.
That is the point of the change, not a side effect — but it must not change filenames for the
single-version majority.

### 4. Filename prefixes follow the resolved scope, not the parameter

Today `_get_version_surveys` prefixes `vN_` whenever the parameter is literally `'all'`, so under a
default of `all` every single-version survey would suddenly download `v1_data.csv` instead of
`data.csv`. Prefixes are therefore driven by `scope.is_family`: one header in scope → no prefix;
more than one → `vN_` on each.

This also fixes a latent oddity: `?version=all` on a single-version survey already produces a
pointless `v1_` prefix today.

### 5. The dashboard's Download button carries the on-screen scope

`analytics_dashboard.html:379` links to `/download` bare. It gets `?version={{ current_version }}`,
so the button exports exactly what the page above it is reporting. This is the shortest path a
creator can walk into the inconsistency, and after the parity fix it stays correct by construction.

## Risks / Trade-offs

- **A multi-version survey's default download changes size.** A creator who bookmarked
  `/download` and expected the current version now gets the family, with `vN_` prefixes. Mitigated
  by: the dropdown still offers "Current (vN)" explicitly, and the previous default was the side of
  the disagreement that under-reported — silently returning 2 of 111 rows is the worse failure.
- **Unknown values stay silent.** `?version=bogus` returns the family with no warning. Both
  surfaces now agree, so it can no longer produce contradictory numbers; a visible error for a
  typo'd bookmark is not worth an error page.
- **`latest` is kept alive.** It is a second name for `vN` and one more thing to remember. Removing
  it would break existing dropdown links and any bookmark made from them.

## Migration Plan

None. No schema, no data. Deployment is a code swap; in-flight bookmarks keep working with the
semantics described above.

## Open Questions

None. The default was chosen deliberately (decision 3).
