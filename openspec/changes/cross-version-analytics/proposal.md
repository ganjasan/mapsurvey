# Cross-version analytics and response counts

## Why

Publishing a new survey version makes every creator-facing counter collapse to zero.
`publish_draft()` moves the old sections *and all sessions* onto a new archived
`SurveyHeader`, while the canonical header receives the draft's cloned questions (new
`Question.id`s, same `code`s). Everything that filters by a single survey object then
goes blind:

- **Dashboard cards** count sessions of the canonical only → "1 started · 0 completed ·
  0% rate" right after publishing (real incidents: Ameelia Mirt 340→1 on 2026-07-06;
  bisqunours republished a 619-response survey to fix a typo and saw 0).
- **Results (analytics)**: `AnalyticsService.base_qs = SurveySession.objects.filter(survey=survey)`
  — table, charts, geo layers, performance tab all show only the new, empty version.
- **Public results blocks**: sessions are already family-wide, but `_answers()` filters
  by the block's single `question` FK. After publish that object lives in the archive, so
  blocks silently stop counting new-version answers (and blocks bound after publish lose
  all historical ones).

The data is intact — this is purely an aggregation-scope problem, and it terrifies users
("мои 300+ ответов пропали").

## What Changes

- **One family scope helper**: a single source of truth for "canonical + all version
  copies" (survey ids, sessions, clean sessions), reused by analytics, dashboard,
  performance and public results instead of ad-hoc `filter(survey=...)`.
- **Question lineage by `code`**: questions sharing a `code` within the family form one
  lineage; answers aggregate across the lineage. An `input_type` change breaks the
  lineage (the archived one reports separately). Lineages whose question no longer exists
  in the canonical version are shown in an **"Archived questions"** group instead of
  disappearing.
- **Dashboard cards** show family-wide started/completed/rate.
- **Results (analytics)** defaults to **All versions** with a version filter (All / v3 /
  v2 …); the sessions table gets a version column; charts/stats/geo layers aggregate by
  lineage; removed choice codes render as flagged "no longer offered" buckets.
- **Public results blocks** resolve answers by lineage (code across family survey ids)
  instead of the single question FK — fixes the silent post-publish freeze in both
  directions.
- **Editor guard against code reuse**: new choice codes are allocated above every code
  ever answered in the lineage, so a freed code can never be silently re-bound to a new
  meaning.
- **Publish dialog copy** explains what analytics will show after publishing (nothing
  disappears; archived lineages stay visible under All versions).

## Capabilities

### New Capabilities

- `cross-version-analytics`: family scope, question lineages, All-versions default with
  a version filter, archived-question group, lineage-aware public-results blocks, choice
  code-reuse guard, publish-dialog messaging.

### Modified Capabilities

- `survey-cards`: dashboard response counts span all versions of a canonical survey.

## Impact

- `survey/versioning.py` (or a new `version_family` helper module): `family_ids()`,
  `family_sessions()`, `lineage_map()`.
- `survey/analytics.py`: services take a version scope (default all), question-level
  aggregation keyed by lineage.
- `survey/editor_views.py` / dashboard queries: family counts.
- `survey/public_results.py`: `_answers()` resolves by lineage.
- `survey/editor_views.py` choices editing: code allocation guard.
- Templates: analytics version filter, archived-question group, dashboard card hint,
  publish modal copy.
- Closes backlog #13 (`improvement-versioning-cross-version-analytics.md`).
