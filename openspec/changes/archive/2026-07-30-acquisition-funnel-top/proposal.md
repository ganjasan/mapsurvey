## Why

The creator funnel dashboard starts at registration, so every question about *acquisition* is
unanswerable from it: we see 40 signups in a month but not how many people saw us in Google, how
many actually landed, or how many tried the demo before deciding. The GTM plan targets
registrations/month, yet the only lever we can currently observe is the last step of the chain —
we are optimising the bottom of a funnel whose top is invisible. Google Search Console access
already exists as a local script (`scripts/gsc_report.py`) and Plausible is live on production;
neither feeds the dashboard, so the numbers are read by hand and never sit next to conversion.

## What Changes

- Add a **top-of-funnel block** to the staff funnel dashboard covering the stages before
  registration: Google impressions → landing visits → registrations → demo opens, with the
  step-to-step conversion rate between each pair.
- Ingest **Google Search Console** metrics (impressions, clicks, CTR, average position) into our
  own database as daily rows via a management command, so the dashboard never calls the GSC API
  during a request.
- Ingest **Plausible** landing metrics (total visitors, pageviews, plus a per-channel referrer
  breakdown) into the same daily store, giving total landing traffic where GSC only sees organic
  Google.
- Count **demo opens** from `SurveySession` rows on the survey behind `DEMO_SURVEY_URL`, reported
  as two separate numbers: anonymous sessions (demo as an acquisition hook, seen before signing
  up) and sessions by authenticated users (demo as onboarding).
- Run the ingestion on a schedule as a **Render Cron Job** (the deployment has a Celery worker but
  no beat scheduler), with an idempotent re-runnable command that backfills a date window.
- Degrade gracefully: a missing credential, an unreachable API, or a not-yet-synced day renders the
  affected metric as "not available" with the reason, and never breaks the rest of the dashboard.
- Rename the `/user-outreach` command to `/gtm-daily` and prepend a metrics-review step to it, so
  the daily ritual starts from the acquisition numbers and only then moves to work with people.

## Capabilities

### New Capabilities
- `acquisition-metrics-sync`: pulling external acquisition metrics (Google Search Console,
  Plausible) into local daily records via a scheduled, idempotent management command, including
  credential handling, the backfill window, and the behaviour when a source is unavailable.

### Modified Capabilities
- `creator-funnel-dashboard`: the dashboard gains a top-of-funnel section covering the
  pre-registration stages (impressions, landing visits, demo opens) and their conversion rates,
  alongside the existing registration→activation funnel.

## Impact

- **New model + migration**: daily acquisition metric rows (source, date, metric set), plus a
  per-source sync-state record for freshness reporting.
- **New service module** for fetching and normalising GSC and Plausible data, and for computing
  demo-open counts; `survey/funnel.py` gains the top-of-funnel block in `dashboard_context()`.
- **Template**: `survey/templates/admin/funnel_dashboard.html` gains the new section.
- **Settings/env**: GSC service-account credentials and `GSC_SITE` must become available to
  production (today the key exists only on the developer machine); a Plausible Stats API key must
  be created in the Plausible account and added as `PLAUSIBLE_API_KEY` / `PLAUSIBLE_SITE_ID`.
- **Deployment**: a new cron service in `render.yaml`.
- **Dependencies**: `google-api-python-client` and `google-auth` move from a script-only
  convenience into `requirements.txt`; Plausible is plain HTTP.
- **Operations**: `~/.claude/commands/user-outreach.md` renamed to `gtm-daily.md`; references to
  `/user-outreach` in project docs updated.
