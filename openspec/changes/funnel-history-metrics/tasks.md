# Tasks — funnel history metrics

## 1. Model and migrations
- [x] 1.1 `SurveyHeader.published_at` (`DateTimeField`, null, indexed)
- [x] 1.2 `MetricSnapshot(date, key, value)`, `unique_together (date, key)`, index `(key, date)`, read-only admin
- [x] 1.3 Migration `0094_published_at_metric_snapshot`
- [x] 1.4 Migration `0095_backfill_published_at`: earliest `AuditLog` publish transition per `survey_uuid`; no-op reverse
- [x] 1.5 `editor_survey_transition`: set `published_at` on the first transition to `published`; `editor_publish_draft` untouched
- [x] 1.6 `funnel._published_first_created` (and `time_to_value`): `Coalesce(published_at, created_at)`

## 2. Series registry and computations
- [x] 2.1 `survey/metrics.py`: `Series`, `SERIES`, `weekly_series(key, start, end)`, `current_state(key)`, `snapshot_series(key, start, end)`, `history_since(key)`
- [x] 2.2 Event series: `regs`, `activations`, `surveys_created`, `surveys_published`, `first_responses`, `responses`, `live_surveys`
- [x] 2.3 State series: `activated_30d`, `active_30d`, `returned_pct`, `publish_rate`, `collecting_unpublished`, each reusing the existing `CreatorFunnelService` computation (`goals()` split into `goal_values()` + cards so there is no second definition)
- [x] 2.4 `tiles(weeks)` → list of tile dicts (current, delta, series, partial_last, history_since)

## 3. Snapshot command and cron
- [x] 3.1 `snapshot_metrics` management command: all state series, `update_or_create`, `--date`
- [x] 3.2 `render.yaml`: cron `mapsurvey-metrics-snapshot`, `10 0 * * *`, `python manage.py snapshot_metrics`
- [ ] 3.3 Run it once by hand after the production deploy (first point on deploy day)

## 4. Dashboard
- [x] 4.1 `admin/_metric_tile.html` + the Chart.js include and the one inline script in `funnel_dashboard.html`
- [x] 4.2 ① Trends section with the two tile rows; the two inline-SVG bar charts and `_funnel_barchart.html` removed; nav renumbered ①–⑧
- [x] 4.3 Period selector drives every tile (`weeks` → event buckets and snapshot days)
- [x] 4.4 Empty / forward-only states: no-chart tile with "history from <date>", proxy notes on `activations` and `surveys_published`

## 5. Tests and docs (GIVEN / WHEN / THEN)
- [x] 5.1 `MetricSeriesTest`: ISO-week buckets, staff excluded, canonical rows only, first responses per survey and external, live vs responses, state = goal card, registry coverage
- [x] 5.2 `PublishedAtTest`: set on first publish only; reopen keeps it; backfill picks the earliest audit row; pre-audit survey stays `NULL` and the proxy applies
- [x] 5.3 `MetricSnapshotTest`: unique per day/key, read-only admin, one row per state series, rerun overwrites, `--date`, range read / `history_since`
- [x] 5.4 `TrendTilesDashboardTest`: one tile per series + one JSON block + one Chart.js tag, running week not compared, state delta over 7 days, deploy day, second day, `?weeks=12|all`
- [x] 5.5 Funnel test classes + the new ones green (41 tests); full suite run before the PR
- [x] 5.6 Browser check on the dev server with seeded data (tiles, deltas, hover tooltip, period selector)
- [x] 5.7 `CLAUDE.md`: paragraph on the series registry, the snapshot table and `published_at`
- [ ] 5.8 Sync `openspec/specs/creator-funnel-dashboard/spec.md` and add `openspec/specs/platform-metric-snapshots/spec.md` on archive
