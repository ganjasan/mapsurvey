# Tasks

## 1. Shared resolver

- [x] 1.1 Add `VersionScope` and `resolve_version_scope(survey, version)` to `survey/versioning.py`:
      normalise falsy → `all`, `latest` → `vN` (canonical), `vN`/`N` → that family member,
      anything unresolvable → `all`. Return `value`, `headers` (canonical first, archived
      newest-first), `ids`, `is_family`.
- [x] 1.2 Replace `resolve_version_scope` in `survey/analytics.py` with a thin wrapper returning
      `.ids`, so `SurveyAnalyticsService`/`PerformanceAnalyticsService` `self.scope_ids` is unchanged.
      `_scope_surveys` now reads the scope's headers instead of re-querying and re-sorting them.
- [x] 1.3 Rewrite `_get_version_surveys` (`survey/views.py`) on top of the shared resolver, with
      `vN_` prefixes only when `scope.is_family`.

## 2. Export default

- [x] 2.1 `download_data` passes the raw parameter through (no per-caller default); the resolver
      supplies `all`.
- [x] 2.2 Verify `include_all=1` and the excluded-session pre-computation still cover every header
      in scope — both already iterate `version_surveys`, which is now the resolved scope.

## 3. UI

- [x] 3.1 Analytics dashboard Download button carries `?version={{ current_version }}`
      (`analytics_dashboard.html:379`).
- [x] 3.2 Export dropdown's `latest` links (`_survey_more_menu.html`) still read correctly — under
      the new semantics `latest` is the canonical version, which is what "Current (vN)" claims.
      No change needed.

## 4. Tests (`survey/tests.py`, GIVEN/WHEN/THEN)

- [x] 4.1 `VersionScopeResolverTest`: default, `all`, `latest`, `vN` canonical, `vM` archived, bare
      `N`, `bogus`, out-of-family `v99`, single-version survey, resolution from an archived header.
- [x] 4.2 `VersionFilterParityTest.test_both_surfaces_resolve_every_value_identically`.
- [x] 4.3 Export tests: no parameter on a multi-version survey yields the family's rows (the
      111-vs-2 case); `latest` narrows both surfaces.
- [x] 4.4 Prefix tests: `version=all` on a single-version survey produces unprefixed filenames;
      on a multi-version survey produces one `vN_` set per version.
- [x] 4.5 Dashboard Download link carries the on-screen version.
- [x] 4.6 Update `test_download_no_version_param_returns_latest` — the default is now the family.

## 5. Verification

- [x] 5.1 `./run_tests.sh survey` green — 1047 tests, OK (1 skipped). (The worktree's venv was
      missing `nh3`, which is in the Pipfile; installing it cleared 5 unrelated errors in the
      thanks-page tests.)
- [x] 5.2 Live check against local data (`Ameelia Mirt`, canonical v3 + archived v2, the
      public-results worktree's db): both columns now match for every row of the backlog table —
      *(none)* 111/111, `latest` 2/2, `all` 111/111, `v3` 2/2, `v2` 109/109, `bogus` 111/111.
      Filenames: prefixed `v3_`/`v2_` for family scopes, unprefixed for single-version scopes.
- [x] 5.3 Strike #114 in `openspec/backlog/INDEX.md` and mark the item file fixed.
