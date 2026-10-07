## Context

`survey/funnel.py::dashboard_context` assembles the staff dashboard from `CreatorFunnelService`
(stage membership sets computed from current rows), `AcquisitionService` (registrations and demo
opens in a window; search metrics live in PostHog) and the cohort system. Only `weekly_signups`
and `weekly_activity` are series; they render through `bar_chart_geometry` as inline SVG. Every
other number is "now".

What the tables can and cannot tell us about the past:

| Fact | Timestamp | History |
|---|---|---|
| registration | `auth_user.date_joined` | since 2026-02-18 |
| account activation | none on `auth_user` (`is_active` flips) | `creator_activated_account` in PostHog since 2026-08; **not** in our DB |
| survey created | `SurveyHeader.created_at` | full |
| first question | `Question` rows carry no timestamp | not derivable |
| survey published | none today; `AuditLog(action='status_transition', metadata.new_status='published')` since migration `0035` | partial |
| response | `SurveySession.start_datetime` | full |
| creator active / returned / dormant | `last_login`, `UserActivity.last_activity`, `updated_at` — each keeps only the latest moment | not derivable |
| publish rate, unclassified share, collecting-unpublished | ratios of current state | not derivable |

The `posthog-funnel-migration` change decided that stage funnels and retention live in PostHog
and that this page keeps acquisition, worklists, radar and abuse, "and stays the fallback while
PostHog's numbers are being trusted". This change does not reopen that: it gives the fallback a
memory, from our own rows, without a second event pipeline.

## Goals / Non-Goals

**Goals:** every metric on the page that is worth watching has a chart over time; the page
distinguishes "measured history" from "history that starts at deploy"; the publish moment becomes
a fact on the survey row; the computation stays cheap enough to run per request at current scale
(hundreds of users, tens of thousands of sessions).

**Non-Goals:** a general event log or a second PostHog; per-survey or per-cohort drill-down on
the tiles; changing the goal targets, the cohort table, the acquisition block, the action lists;
touching respondent analytics (`SurveyEvent`); a time-series database — a table of
`(date, key, value)` rows is the whole mechanism.

## Decisions

**D1. Two series kinds, declared in one registry.** `survey/metrics.py` defines
`Series(key, label, kind, unit, note)` and the ordered tuple `SERIES`. `kind='event'` series have
a `weekly(start, end)` computation over timestamps and are retro-active; `kind='state'` series
have a `current()` computation and are read back from `MetricSnapshot`. The dashboard, the
snapshot command and the tests iterate the same tuple, so a series added to the registry is
snapshotted, charted and tested without a second list. The registry is code, not a table: the
set changes in PRs, and a row that is not understood by the computation is worth nothing.

The core, in page order:

| key | kind | definition |
|---|---|---|
| `regs` | event, weekly | real users by `date_joined` (staff/superusers excluded, as everywhere on the page) |
| `activations` | event, weekly | real users with `is_active` by `date_joined` — *proxy*: activation has no timestamp of its own; the tile says "by signup week" |
| `surveys_created` | event, weekly | `SurveyHeader` by `created_at`, `created_by` not null, canonical rows only (no draft copies / versions) |
| `surveys_published` | event, weekly | `SurveyHeader` by `published_at`; rows with `NULL` are outside the series and the tile states the audit start date |
| `first_responses` | event, weekly | surveys whose earliest non-deleted `external` session falls in the week (`Min(start_datetime)` per survey) |
| `responses` | event, weekly | non-deleted sessions by `start_datetime` (today's `weekly_activity`) |
| `live_surveys` | event, weekly | distinct surveys with ≥1 non-deleted session in the week |
| `activated_30d` | state, daily | the North Star card's number, from the same `goals()` computation (real users registered in the last 30 days with ≥5 responses) — one definition, not two |
| `active_30d` | state, daily | `active_user_metrics()['active_30']['count']` |
| `returned_pct` | state, daily | `active_user_metrics()['returned']['pct']` |
| `publish_rate` | state, daily | `goals()`'s publish-rate percentage |
| `collecting_unpublished` | state, daily | `len(collecting_unpublished(limit=None))` |

Five event series are the creator funnel laid side by side; `first_question` is absent because
`Question` has no timestamp and inventing one is not this change's business. `activations` is a
proxy by design and labelled as such — the alternative, adding an `activated_at` to the user
model, is a `django_registration` signal and a migration on `auth_user`'s companion table for a
column PostHog already has; deferred unless the proxy misleads in practice.

**D2. `MetricSnapshot(date, key, value)`.** `date` (`DateField`), `key` (`CharField(40)`),
`value` (`FloatField` — counts and percentages share one column; a count is a whole float),
`unique_together (date, key)`, index on `(key, date)`. No FK, no JSON: a row is one number on one
day, which is what a line chart consumes. The table is written only by `snapshot_metrics` and is
read-only in the admin (registered, list view, no add/change). The "no new data table"
requirement of the dashboard spec was written for stages derivable from rows; it gains an
explicit exception for state series, with the same obligation the forward-only acquisition stages
already carry: say when recording started.

**D3. `snapshot_metrics` is idempotent per day.** It computes every `state` series with
`current()` and `update_or_create`s `(date=today, key)`. Rerunning it overwrites the same rows,
so a double-fired cron or a manual run after a fix is harmless. `--date YYYY-MM-DD` writes rows
for that date from *today's* state — useful for tests and for repairing a missed day with a
clearly-labelled approximation, never for pretending to backfill. The Render cron
`mapsurvey-metrics-snapshot` runs `python manage.py snapshot_metrics` at `00:10` UTC (a single
command, so no shell wrapper is needed — `reclaim.sh` exists because of `&&`). The command prints
one line per run and lets an exception propagate, so a failed night is a failed cron run in the
Render dashboard rather than a silently missing point (it is not a Celery task, so the
`task_failure` receiver does not see it).

**D4. `SurveyHeader.published_at` holds only the truth.** `DateTimeField(null=True, db_index=True)`,
set in `editor_survey_transition` when `new_status == 'published'` and the field is `NULL` — the
first publish, not the latest reopen; `editor_publish_draft` publishes a *new version* of an
already-published survey and leaves it alone. Migration `0095` backfills from
`AuditLog.objects.filter(action='status_transition', metadata__new_status='published')`, earliest
row per `survey_uuid`, matching on `SurveyHeader.uuid`. A survey published before the audit log
existed stays `NULL`; `_published_first_created` becomes `Coalesce(published_at, created_at)` so
the cohort table's `Pub ≤14d` column improves where the fact exists and keeps today's proxy where
it does not. The PostHog backfill's `timestamp_source` vocabulary already describes this split.

**D5. Chart.js, one tile partial, data as JSON.** `admin/_metric_tile.html` takes a tile dict
(`key, label, unit, note, current, delta, series=[{x, y}], partial_last`) and renders the
header, the value, the delta pill and a `<canvas>`. One `<script type="application/json"
id="metric-tiles">` carries every series; one inline script builds the charts (line, no
legend, no animation, tooltip = period + value, the last point drawn hollow when `partial_last`
— the current ISO week or today). Chart.js `4.4.0` from jsDelivr, the version and host
`analytics_dashboard_v2.html` already pins, so the admin page adds no new third-party origin.
`bar_chart_geometry` stays for the cohort sparklines, which are table cells and gain nothing from
a canvas.

**D6. Buckets and deltas.** Event series are bucketed by ISO week (`TruncWeek`, Monday start,
UTC like the rest of the page) over the selected period; the last bucket is the running week.
State series are daily points over the same period in days. The tile's *current* value is the
last complete bucket for event series (the running week is shown on the chart but not compared —
a Tuesday is not a week) and the latest snapshot for state series; *delta* is current minus the
bucket before (event) or minus the value seven days earlier (state), rendered as a signed number
and a tone (up is green for everything in the core — there is no "lower is better" series in it;
`collecting_unpublished` is a worklist size and shows the number without a tone).

**D7. Missing history is shown as missing.** A state tile with fewer than two snapshots renders
its current live value with "history from <first snapshot date or today>" and no chart; a state
tile with no snapshot at all computes `current()` live so the page never shows a blank on deploy
day. `surveys_published` says "recorded publishes since <date of the first AuditLog publish
row>"; `activations` says "by signup week". The existing scenario *Forward-only stages state their
start date* covers all three.

**D8. Page order.** ① Trends (the tiles, two rows: funnel series then state series) → ② Goals →
③ Acquisition → ④ This week → ⑤ Audience → ⑥ Monthly cohorts → ⑦ Living users (cards and the
top-surveys table; the two bar charts are gone, their series are tiles) → ⑧ Actions. The nav
strip and anchors follow. Goals keep their cards; their history is the `activated_30d`,
`regs` and `publish_rate` tiles one section up, so the cards do not grow sparklines.

## Risks / Trade-offs

- **Per-request cost grows** by seven grouped queries and up to five `MetricSnapshot` reads.
  `active_user_metrics` already walks every user in Python; the page is staff-only and was
  within budget at ~300 users. If it slows, cache `dashboard_context` for five minutes — the
  docstring has said so since the first version and still applies.
- **The snapshot cron is another moving part.** A missed night is a gap in a line, not a wrong
  number; the admin list of `MetricSnapshot` shows the last date at a glance, and a
  `snapshot_metrics` rerun fills today. Nothing else depends on the table.
- **`activations` by signup week is not activations by activation week.** For a cohort that
  activates within a day the two agree; a late activation lands in the past. Labelled on the tile;
  PostHog has the exact series.
- **Chart.js on the admin page** brings a CDN script where there was none. Staff browsers run
  blockers too; the tile shows value and delta in HTML, so a blocked script loses the curve, not
  the number.

## Migration Plan

`0094_published_at_metric_snapshot` adds the column and the table; `0095_backfill_published_at`
is a `RunPython` over `AuditLog` (reverse is a no-op — the column goes with `0094`'s reverse).
Deploy order is free: the dashboard reads `NULL` as "proxy" and an empty snapshot table as
"history starts today". The cron appears with `render.yaml`; the first snapshot is the first
night after deploy, and running `snapshot_metrics` once by hand on deploy day gives the tiles
their first point.
