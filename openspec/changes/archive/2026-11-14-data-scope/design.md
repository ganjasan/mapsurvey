## Context

ADR-001 (ops `requirements/adr/`) found the "which sessions count" rule written by hand across the
code: `public_results._collect_clean_session_ids` with `EXCLUDED_VALIDATION_STATUSES`,
`layers.clean_session_filter` (shared-map objects), four filters in `object_stats.py`,
`export.excluded_sessions` (which `response_scope.responses_scope` and therefore API v1/MCP reuse),
`analytics.SurveyAnalyticsService.base_qs` and six `survey_session__is_deleted=False` answer
filters, `analytics_views.py` choice filtering, `versioning.family_sessions`, `comments.session_seq`,
`api/v1/structure.py` (counts trashed sessions), `mcp/tools/surveys.py`. They disagree on three
points the owner decided on 2026-11-14 (ADR-001 §6.1, §6.2, §6.5). Data (epic #676) is next to
read the same sessions, so the rule moves into one module first.

## Goals / Non-Goals

**Goals:**
- One builder, `data.scope.SessionScope`, for every set-of-sessions read; switches are named
  parameters, not per-surface filters.
- Apply decisions §6.1 (export drops `on_hold` unless `include_all`), §6.2 (`/r/` and Site results
  blocks count non-empty sessions only) and §6.5 (Responses keeps moderated sessions, says so).
- A ratchet test so no new hand-written copy appears.

**Non-Goals:**
- Aggregation and masking (`data.aggregate`, `data.features`) — #666; k-anonymity on API reads
  (§6.3) is undecided and untouched here.
- `/r/` access control for trashed or password surveys (§6.4) — ADR move 4.
- Moving models or tables; the package split (move 6).
- Staff funnel dashboards (`funnel.py`) and single-session lookups: they stay, listed in the guard.

## Decisions

**D1 — A top-level `data` package, plain Python for now.** `data/__init__.py` + `data/scope.py`.
No models, so it is not added to `INSTALLED_APPS` until #667 brings the dataset registry. It
imports `survey.models` (tables stay in `survey`, ADR §4). Alternative — `survey/scope.py` — would
need moving again in move 6 and hides the boundary the guard test enforces.

**D2 — The shape.**

```python
SessionScope(survey_ids, *, include_deleted=False, include_moderated=False,
             nonempty=False, completed_headers=None, external_only=False)
  .sessions()            -> SurveySession queryset
  .ids()                 -> set of ids
  .q(prefix)             -> Q for a related queryset (Answer: 'survey_session', LayerObject: 'source_session')
SessionScope.public(survey)              # family, clean, nonempty      → /r/, Site results blocks
SessionScope.for_family(survey, **kw)    # family ids from versioning.family_ids
```

`include_moderated` keeps `on_hold` and `not_approved`; `include_deleted` keeps trashed sessions;
`nonempty` is the one emptiness predicate (moved from `analytics._has_top_level_answer`;
`nonempty_sessions`/`empty_sessions` stay as thin wrappers so the empty-sessions spec and callers
keep their names); `completed_headers` applies `completed_session_filter` against those headers.
`q()` expresses deleted/moderated as field lookups and nonempty/completed as `__in` subqueries, so
it composes with any related queryset without a second definition. Version resolution stays in
`versioning` — the scope takes ids, never parses `version`.

**D3 — Surface mapping.**

| Surface | Scope |
|---------|-------|
| `/r/`, Site results blocks (`PublicResultsService`) | `public(survey)` — clean + nonempty (**§6.2 change**) |
| Shared-map objects and tallies (`layers`, `object_stats.shared_map_*`) | clean via `q('source_session' / 'survey_session')` (unchanged meaning) |
| Object statistics for Responses (`object_aggregates`, `layer_object_stats`) | `include_moderated=True` via `q()` (unchanged meaning) |
| Export session gate (`export.excluded_sessions`) | kept = `include_deleted=include_all, include_moderated=include_all, nonempty=True, completed_headers=…` (**§6.1 change**: `on_hold` joins the excluded set) |
| API v1 / MCP responses scope | through the export gate (follows §6.1) |
| Responses (`SurveyAnalyticsService`) | `include_moderated=True`, `include_deleted` as before, `nonempty=not include_empty`; answer filters through `q()` |
| `analytics_views` choice filter, `comments.session_seq`, `versioning.family_sessions` | the Responses scope (unchanged meaning) |
| API structure `responses` count | Responses scope + nonempty (fix: no longer counts trashed sessions) |
| MCP survey response count | `external_only=True, include_moderated=True, nonempty=True` (unchanged meaning) |
| First-response signal (`signals.py`) | `external_only=True, include_moderated=True` on one survey (unchanged) |

**D4 — Responses names moderated responses (§6.5).** `SurveyAnalyticsService.moderated_counts()`
returns `{'on_hold': n, 'not_approved': m}` over the shown scope; `_empty_sessions_toggle.html`'s
sibling line renders "including N on hold · M not approved" only when either is non-zero. Three
new msgids go into every offered catalog by hand (like PR #274), not `makemessages`.

**D5 — Export dialog text.** "Trashed and not-approved responses are left out unless you switch
this on." becomes "Trashed, on-hold and not-approved responses are left out unless you switch this
on." New msgid in every offered catalog; the old one stays only if another template uses it.

**D6 — Guard as a ratchet.** `survey/tests/test_session_scope.py::SessionFilterGuardTest` scans
non-test, non-migration `.py` files in `survey/`, `api/`, `mcp/`, `billing/`, `newsletter/`,
`mapsurvey/` for hand-written session filters — keyword `is_deleted=` (not attribute assignment),
`__is_deleted`, `validation_status__in`, `exclude(validation_status`, `_has_top_level_answer` — and
compares per-file counts with `ALLOWED_SESSION_FILTERS = {path: (count, reason)}`. A file not in
the map, or above its count, fails; a file below its count fails the stale-entry test (the map may
only shrink), the same pattern as `SpecTestLineageTest`. Entries left after this change:
single-session lookups (`views.py`, `analytics_views.py` restore/trash, `paper/*`,
`operator_entry_views.py`, `api/v1/responses.py` detail), staff dashboards (`funnel.py`,
management commands), the model field and manager (`models.py`).

## Risks / Trade-offs

- [Public result counts drop on live pages] → expected by §6.2; frozen snapshots keep their
  stored numbers; the change note says so.
- [API/MCP clients see fewer sessions without `include_all`] → noted in the API changelog; the
  numbers still equal the export file, which was the API's promise.
- [Subquery cost of `nonempty` on `/r/`] → it already runs on Responses for the same surveys;
  `/r/` live data is cached for 60 s.
- [Guard regex misses an exotic spelling] → it targets the spellings the ADR counted; review
  catches the rest, and `data.scope` is the documented path in `CLAUDE.md`.

## Migration Plan

Code only. Deploy with the epic merge (`epic/data` → `master`). Rollback = revert the merge; no
data changes.

## Open Questions

None for this change; §6.3 and §6.4 belong to #666 and move 4.
