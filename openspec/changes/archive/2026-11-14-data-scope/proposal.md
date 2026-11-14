## Why

Which sessions count is decided by hand in a dozen places, and the copies disagree: the export
keeps `on_hold` sessions that the public results page drops, the public results page counts empty
sessions that Responses hides and the export never contains, layer tallies and object statistics
carry their own copy of the "clean" rule, and the API's per-survey response count includes trashed
sessions. The platform is about to add three more readers of the same sessions — Data datasets,
Map apps tallies and Reports — so the rule must live in one place first. This is move 1 (with move
0, the guard) of ADR-001 and the first item of the Data epic (#676, issue #665).

## What Changes

- A new top-level package `data/` with one module, `data.scope`: `SessionScope` builds the
  session queryset for a survey family with named switches (`clean`, `nonempty`, `completed`,
  `external_only`, `include_moderated`) instead of hand-written filters.
- The public results page, Site results blocks (through the same service), layer tallies and
  shared-map materialisation, object statistics, the export's session gate, the API/MCP response
  scope, the API structure count, the MCP survey count and the Responses analytics service build
  their session sets through `SessionScope`. `EXCLUDED_VALIDATION_STATUSES`,
  `layers.clean_session_filter` and the private clean-id collectors go.
- **BREAKING (export)**: `on_hold` sessions are left out of every export format unless
  `include_all=1` (owner decision ADR-001 §6.1). The API export link, summary, text answers and
  GeoJSON, which count what the export contains, change with it. The export dialog's switch text
  names on-hold responses.
- **BREAKING (public results)**: the response counter and every aggregate on `/r/` and in Site
  results blocks count only non-empty sessions — the same responses Responses shows (§6.2). Frozen
  snapshots are not recomputed.
- Responses keeps showing `on_hold` and `not_approved` sessions (the creator moderates there), as
  the scope's named `include_moderated` switch, and its headline says how many of the responses are
  on hold or not approved (§6.5).
- A guard test fails when a new hand-written session filter (`is_deleted`, `validation_status`,
  the empty-session predicate) appears in a non-test module outside `data/` and outside an
  allow-list that may only shrink; single-session lookups and staff dashboards are listed with a
  reason. `CLAUDE.md` states the rule.

## Capabilities

### New Capabilities
- `session-scope`: the one definition of which sessions a surface counts — the switches, their
  meaning, the surfaces bound to it and the guard against new copies.

### Modified Capabilities
- `responses-export-formats`: excluded sessions now include `on_hold` unless `include_all`; the
  dialog says so.
- `public-results-page`: the clean-session data source excludes empty sessions, so counts equal
  Responses'.
- `responses-empty-sessions`: the shared emptiness helper is the scope's `nonempty` switch, and the
  Responses headline names moderated responses.

## Impact

- Code: new `data/__init__.py`, `data/scope.py`; rewired `survey/public_results.py`,
  `survey/layers.py`, `survey/object_stats.py`, `survey/export.py`, `survey/response_scope.py`,
  `survey/analytics.py` (base queryset, language list, counts), `api/v1/structure.py`,
  `mcp/tools/surveys.py`; Responses headline partial; export dialog string (all offered catalogs).
- Behaviour visible to users: export without `include_all` loses on-hold sessions; public result
  counts drop by the number of empty sessions. API v1/MCP numbers follow the export (noted in the
  API changelog). No change to respondent pages, Responses table contents or the funnel pane.
- No migration, no model change, no new dependency.
- Tests: a new `survey/tests/test_session_scope.py` (module per capability) plus updated
  expectations in export, public results and API tests that pinned the old behaviour.
