## 1. The scope

- [x] 1.1 Create `data/__init__.py` and `data/scope.py` with `SessionScope` (switches `include_deleted`, `include_moderated`, `nonempty`, `completed_headers`, `external_only`; `sessions()`, `ids()`, `q(prefix)`; constructors `for_family`, `public`) — D1, D2
- [x] 1.2 Move the emptiness predicate into `data.scope`; keep `analytics.nonempty_sessions` / `empty_sessions` as thin wrappers over it
- [x] 1.3 `survey/tests/test_session_scope.py`: default clean scope, each switch, `q()` on answers and layer objects, `completed_headers`, `external_only` (GIVEN/WHEN/THEN docstrings)

## 2. Rewire the surfaces (D3)

- [x] 2.1 `public_results.PublicResultsService` → `SessionScope.public(survey)`; drop `EXCLUDED_VALIDATION_STATUSES` and `_collect_clean_session_ids` (§6.2)
- [x] 2.2 `layers.clean_session_filter`, `visible_objects`, `creator_objects` and `object_stats.shared_map_tallies` / `shared_map_comments` → clean scope `q()`
- [x] 2.3 `object_stats.object_aggregates` / `layer_object_stats` → Responses scope `q()` (moderated included)
- [x] 2.4 `export.excluded_sessions` → kept set from `SessionScope(include_deleted=include_all, include_moderated=include_all, nonempty=True, completed_headers=…)`; on-hold leaves the default export (§6.1)
- [x] 2.5 `SurveyAnalyticsService`: `base_qs`, `_session_filter`, `_active_scope_qs`, the language list and the answer filters at lines ~604/830/1003/1042/1073 → the Responses scope
- [x] 2.6 `analytics_views` choice filter, `comments.session_seq`, `versioning.family_sessions`, `signals` first-response check, `public_results_editor` answer counts → their scopes
- [x] 2.7 `api/v1/structure.py` responses count (no longer counts trashed) and `mcp/tools/surveys.py` count → scopes
- [x] 2.8 Update tests that pinned the old behaviour (export with on-hold, `/r/` counting empty sessions, structure count) and add the spec scenarios: on-hold absent/present with `include_all`, API summary equals the file, `/r/` counter ignores empty sessions, Site results block same count

## 3. Responses and the export dialog (D4, D5)

- [x] 3.1 `SurveyAnalyticsService.moderated_counts()`; the headline line "including N on hold · M not approved" next to `_empty_sessions_toggle.html`, rendered only when non-zero
- [x] 3.2 Export dialog string names on-hold responses
- [x] 3.3 New msgids appended by hand to every offered catalog and compiled; `TranslationCatalogHygieneTest` green
- [x] 3.4 Tests: headline names moderated responses / carries nothing when there are none; dialog text

## 4. Guard and docs (D6)

- [x] 4.1 `SessionFilterGuardTest` with `ALLOWED_SESSION_FILTERS` (count + reason per module) and its stale-entry test
- [x] 4.2 `CLAUDE.md`: a "Session scope (`data.scope`)" paragraph — the rule, the switches, the guard
- [x] 4.3 API changelog / generated reference note: summaries and exports leave out on-hold sessions unless `include_all`

## 5. Verify

- [x] 5.1 `./run_tests.sh survey api mcp billing newsletter` green (one baseline before, one after)
- [x] 5.2 `openspec validate data-scope --strict`
