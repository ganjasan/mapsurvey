## 1. One definition of "empty"

- [x] 1.1 Add `nonempty_sessions(qs)` and `empty_sessions(qs)` to `survey/analytics.py` (an `Exists` on top-level `Answer` rows), with GIVEN/WHEN/THEN tests: object answer counts, moderator-hidden answer counts, child-only session is empty
- [x] 1.2 Make `compute_session_issues` decide `empty` through the helper; existing `AutoValidationBasicTest` stays green

## 2. Responses service

- [x] 2.1 `SurveyAnalyticsService(..., include_empty=True)`: filter `base_qs` when False; expose `empty_count` over the unfiltered scope; apply the same filter in `_stats_language`; leave the trash branch of `get_table_page` unfiltered
- [x] 2.2 Sequence numbers in `get_table_page`, `needs_review` and `latest_feed` rank non-empty sessions only; empty rows get no number
- [x] 2.3 `comments.session_seq` uses the same rule; a comment on an empty session is labelled "Response without answers"; update `CommentDeepLinkTest` / `CommentA11yMarkupTest`
- [x] 2.4 Service tests: KPIs, completion rate, feeds and table counts with `include_empty` False and True; default True leaves the survey list and legacy dashboard unchanged

## 3. Responses page (v2)

- [x] 3.1 `analytics_dashboard` and `analytics_table` read the `rv2_show_empty` cookie and pass `include_empty` only on the v2 path; legacy template path unchanged
- [x] 3.2 KPI strip and table toolbar: "N responses · M opened without answering" + Show/Hide control when M > 0; control sets/clears the cookie and reloads; tab badge counts shown sessions
- [x] 3.3 Overview empty state: when every session in scope is empty, add the "M opened without answering" line with the Show control
- [x] 3.4 Remove "Empty sessions" from the v2 Issues menu and the mobile issues sheet; keep the "Empty" row badge when empties are shown
- [x] 3.5 View tests: default hides, cookie shows, version switch keeps the choice, trash lists deleted empty sessions, no line when M = 0, Issues menu has no empty entry
- [x] 3.6 Localise the new strings (EN source, RU catalog) and check them with the language cookie

## 4. Export

- [x] 4.1 `export.excluded_sessions` adds empty sessions unconditionally; tests across xlsx, csv and the legacy zip (GeoPackage/Shapefile/KML read the same bundle through the same gate, not tested separately), including `include_all=1` and `completed_only=1`
- [x] 4.2 Export dialog: one line under the switches saying sessions without answers are not exported

## 5. Section POST whitespace

- [x] 5.1 Main POST loop: blank test on the stripped value; store stripped values for text, text_line, datetime, number, range
- [x] 5.2 `_parse_object_fields`: same blank test and stripping for object answers
- [x] 5.3 Tests: "   " in text creates no answer, "  " in number saves without a 500, "  bus stop  " is stored trimmed, object text answer of spaces creates no row

## 6. Ship

- [x] 6.1 Changelog entry `survey/changelog/<release-date>-empty-sessions-hidden.html` (#227 format): what changed, why, and that response numbers now count responses only
- [x] 6.2 Update `CLAUDE.md` Responses notes: empty-session helper, cookie, sequence rule, export exclusion
- [x] 6.3 Measure `get_table_page` and the dashboard with the `Exists` filter — done locally on 2500 synthetic sessions (production psql was not reachable from the worktree sandbox): with planner statistics, hiding is as fast as or faster than showing (overview + extras 0.29 s vs 0.46 s); without ANALYZE each `Exists` query cost ~0.3 s, so a freshly loaded table can be slow until autovacuum analyzes it
- [x] 6.4 Run the full suite once (2262 tests, OK, 1 skipped); drive the Responses page in a browser with and without empty sessions shown
