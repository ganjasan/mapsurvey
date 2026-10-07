# Tasks — funnel history metrics

## 1. Model and migrations
- [ ] 1.1 `SurveyHeader.published_at` (`DateTimeField`, null, indexed)
- [ ] 1.2 `MetricSnapshot(date, key, value)`, `unique_together (date, key)`, index `(key, date)`, read-only admin
- [ ] 1.3 Migration `0094_published_at_metric_snapshot`
- [ ] 1.4 Migration `0095_backfill_published_at`: earliest `AuditLog` publish transition per `survey_uuid`; no-op reverse
- [ ] 1.5 `editor_survey_transition`: set `published_at` on the first transition to `published`; `editor_publish_draft` untouched
- [ ] 1.6 `funnel._published_first_created`: `Coalesce(published_at, created_at)`

## 2. Series registry and computations
- [ ] 2.1 `survey/metrics.py`: `Series`, `SERIES`, `weekly_series(key, start, end)`, `current_state(key)`, `snapshot_series(key, start, end)`
- [ ] 2.2 Event series: `regs`, `activations`, `surveys_created`, `surveys_published`, `first_responses`, `responses`, `live_surveys`
- [ ] 2.3 State series: `activated_30d`, `active_30d`, `returned_pct`, `publish_rate`, `collecting_unpublished`, each reusing the existing `CreatorFunnelService` computation (no second definition)
- [ ] 2.4 `tiles(weeks)` → list of tile dicts (current, delta, series, partial_last, history_since)

## 3. Snapshot command and cron
- [ ] 3.1 `snapshot_metrics` management command: all state series, `update_or_create`, `--date`
- [ ] 3.2 `render.yaml`: cron `mapsurvey-metrics-snapshot`, `10 0 * * *`, `python manage.py snapshot_metrics`, same env block pattern as the reclaim cron
- [ ] 3.3 Run it once by hand after the production deploy (first point on deploy day)

## 4. Dashboard
- [ ] 4.1 `admin/_metric_tile.html` + the Chart.js include and the one inline script in `funnel_dashboard.html`
- [ ] 4.2 ① Trends section with the two tile rows; remove the two inline-SVG bar charts from Living users; renumber the nav
- [ ] 4.3 Period selector drives every tile (`weeks` → event buckets and snapshot days)
- [ ] 4.4 Empty / forward-only states: no-chart tile with "history from <date>", proxy notes on `activations` and `surveys_published`

## 5. Tests and docs (GIVEN / WHEN / THEN)
- [ ] 5.1 Series: each event series buckets by ISO week and excludes staff / deleted / non-canonical rows as specified
- [ ] 5.2 `published_at`: set on first publish only; backfill picks the earliest audit row; pre-audit survey stays `NULL` and the proxy applies
- [ ] 5.3 `snapshot_metrics`: writes one row per state series; rerun on the same day overwrites, not duplicates; `--date`
- [ ] 5.4 Dashboard: tiles render with current + delta, running week not compared, state tile without history shows live value and start date, HTTP 200 for `?weeks=12|26|all`
- [ ] 5.5 Run `./run_tests.sh survey.tests.CreatorFunnelServiceTest survey.tests.FunnelDashboardAdminAccessTest survey.tests.FunnelActivationStagesTest` plus the new classes, then the full suite once
- [ ] 5.6 Browser check on the dev server with seeded data
- [ ] 5.7 `CLAUDE.md`: a paragraph under the acquisition-metrics section on the series registry, the snapshot table and `published_at`
- [ ] 5.8 Sync `openspec/specs/creator-funnel-dashboard/spec.md` and add `openspec/specs/platform-metric-snapshots/spec.md` on archive
