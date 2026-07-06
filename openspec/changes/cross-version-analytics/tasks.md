# Tasks — cross-version-analytics

## 1. Family scope foundation

- [ ] 1.1 `family_ids(survey)` / `family_sessions(survey, include_deleted=False)` /
      `lineage_map(canonical)` next to the versioning helpers; lineage key
      `(code, input_type)`, carrying per-version questions, current question (or None)
      and a version-range label
- [ ] 1.2 Refactor `PublicResultsService._collect_survey_ids` onto `family_ids()`
- [ ] 1.3 Unit tests: family resolution (canonical, archived copies, draft copies
      excluded), lineage merge, lineage break on `input_type` change, version ranges

## 2. Analytics (Results space)

- [ ] 2.1 `AnalyticsService(survey, version='all')`: `'all'` → family sessions,
      `'vN'` → single version; same for the performance service and trash view
- [ ] 2.2 Question-level aggregation keyed by lineage; choice buckets = current choices ∪
      historically answered codes, absent codes flagged "no longer offered"
- [ ] 2.3 Archived lineages (no current question) rendered in an "Archived questions"
      group after the canonical structure, labeled with the version range
- [ ] 2.4 Version filter UI in Results (All versions default / per version); version
      chip column in the sessions table; geo layers built per lineage
- [ ] 2.5 Tests: post-publish analytics still reports family counts; per-version filter
      isolates one version; type-changed lineage reports as two; removed choice code
      appears flagged, not merged or dropped

## 3. Dashboard cards

- [ ] 3.1 Family-wide started/completed/rate on dashboard cards (grid and list views),
      efficient (one grouped query, no N+1)
- [ ] 3.2 Test: card counts unchanged by publishing a new version

## 4. Public results blocks

- [ ] 4.1 `_answers()` (and point-label collection) resolve by lineage across
      `family_ids` instead of the single question FK
- [ ] 4.2 Tests: block bound pre-publish keeps counting post-publish answers; block
      bound post-publish sees historical answers; k-anonymity still masks small buckets

## 5. Write-time guards

- [ ] 5.1 Choice-code allocation: next code = max(current ∪ answered-in-family) + 1;
      reject manual reuse of a historically answered code for a renamed choice
- [ ] 5.2 Family-wide uniqueness check on manual question-code edits
- [ ] 5.3 Tests for both guards

## 6. Messaging & export

- [ ] 6.1 Publish/Force-publish modal copy: state that responses stay visible under
      All versions and breaking changes move to the Archived group
- [ ] 6.2 `survey_version` column in CSV export; archived-lineage columns suffixed with
      their version range
- [ ] 6.3 Verify delete-survey removes sessions and headers across the whole family
      (PROTECT order); add a test

## 7. Verification

- [ ] 7.1 Full `./run_tests.sh survey` green
- [ ] 7.2 Manual: Ameelia Mirt (v3 canonical, 340 sessions on v2) — dashboard card shows
      340/104, Results defaults to All versions, public results blocks live, version
      filter isolates v3's single session
