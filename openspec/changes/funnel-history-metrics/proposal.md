## Why

The staff dashboard at `/admin/survey/funnelreport/` answers "where are we now" and almost never
"where were we". Of its fifteen blocks, two are time series (weekly registrations, weekly
responses); everything else — the goal cards, active 7/30/90, returned/dormant, publish rate,
time-to-value, the audience mix — is a snapshot of the current table state. So the page cannot
show whether a change moved a number: there is no "before" on it, and a point-in-time value
that was 31 last month and is 31 today reads the same as one that was 12.

The `posthog-funnel-migration` analysis named the cause (the dashboard is a state reconstruction,
not an event log) and moved the stage funnel to PostHog. The owner still wants the in-house page
to carry history — it is the one place that reads our own tables, keeps the worklists and stays
the cross-check for PostHog — and wants its metric set rethought around what is worth watching
over time rather than everything that can be counted.

## What Changes

- **A metric core of time series**, replacing the two bar charts and the point-in-time cards as
  the first thing on the page: weekly registrations → activations → surveys created → surveys
  published → surveys with a first response (the creator funnel as five parallel series), plus
  weekly responses and weekly live surveys; daily activated creators (30d, the North Star), active
  creators (30d), returned share, publish rate and the "collecting but unpublished" count. Each
  renders as a compact chart tile with the current value and the change against the previous
  period.
- **Two kinds of series, two sources of history.** Series derivable from timestamps on existing
  rows (`date_joined`, `created_at`, `start_datetime`, `published_at`) are computed live and are
  retro-active to the first signup. Series that describe a state (active, returned, publish rate,
  …) are read from a new `MetricSnapshot` table written once a day by a `snapshot_metrics`
  management command on a Render cron; their history starts on the deploy day and the page says
  so.
- **`SurveyHeader.published_at`**: the real first-publish moment, set on the transition and
  backfilled from the `AuditLog` `status_transition` rows that have recorded publishes since
  migration `0035`. Surveys published before that keep `NULL` and the funnel falls back to the
  creation proxy at read time, exactly as it does today — the column never holds a guess. This
  closes task 1.7 that `posthog-funnel-migration` deferred.
- **Chart.js on the admin page.** The tiles use Chart.js 4 from the CDN the creator pages already
  load it from; hovering a point shows the value and the week, which the inline-SVG bars cannot
  do and which is the whole point of a history chart. The cohort sparklines stay inline SVG.
- The period selector (12 / 26 / all weeks) now governs every tile. Goals, acquisition, the
  audience mix, the cohort table, the action lists, the cluster radar and the abuse summary are
  unchanged.

## Capabilities

### New Capabilities
- `platform-metric-snapshots`: the `MetricSnapshot` table, the series registry, the daily
  `snapshot_metrics` command and its cron.

### Modified Capabilities
- `creator-funnel-dashboard`: the trends section replaces the weekly charts; the "no new data
  table" rule gets the snapshot exception; the period selector covers all tiles; `published_at`
  feeds the publish-window column.

## Impact

- `survey/models.py` (`SurveyHeader.published_at`, `MetricSnapshot`) + migrations `0094`
  (schema) and `0095` (backfill from `AuditLog`).
- `survey/metrics.py` (new: series registry and the weekly/daily computations),
  `survey/funnel.py` (`dashboard_context` builds the tiles; `_published_first_created` prefers
  `published_at`), `survey/editor_views.py` (set `published_at` on the transition).
- `survey/management/commands/snapshot_metrics.py` (new), `render.yaml` (cron
  `mapsurvey-metrics-snapshot`).
- Templates: `admin/funnel_dashboard.html`, new `admin/_metric_tile.html`; `survey/tests.py`;
  `CLAUDE.md` paragraph; the `creator-funnel-dashboard` spec.
