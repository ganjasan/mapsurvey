# Proposal: web-plan-standard

## Why

On 2026-09-15 the production web service hit Render's 512 MB Starter limit. Eleven
gunicorn workers were SIGKILLed between 04:33 and 06:42 UTC while a creator uploaded
2–4.5 MB reference layers, then the whole container was restarted three times between
15:00 and 15:24 UTC on an 8.8 MB / 1620-object upload; a respondent lost six section
submissions to 502 during those restarts. The instance idles at 425–480 MB (two gthread
workers, never recycled), so any layer upload or ZIP import — both run in the web process
and hold several copies of the parsed file — is enough to cross the limit. The sizing note
in `render.yaml` (~110 MB per worker, 143 MB steady) predates reference layers and is off
by 3×.

## What changes

- `render.yaml`: the web service moves from `starter` (0.5 CPU / 512 MB) to `standard`
  (1 CPU / 2 GB). PR previews stay on `starter` through `previewPlan`: they exist for
  review, and the k6 lecture-burst harness deliberately measures on the slower box.
- The gunicorn sizing comment states the measured numbers instead of the stale estimate.
- `CLAUDE.md` load-testing note names the preview plan, not production's.

The plan is changed in the Blueprint and not in the dashboard: a dashboard-only change is
overwritten by the next Blueprint sync.

## Out of scope

Making layer upload and ZIP import cheaper or asynchronous (parse once, hand off to
Celery), gunicorn `--max-requests` recycling, and the `purge_survey` `ProtectedError` on
surveys with a layer-bound question. Each is its own change.

## Impact

- Cost: Starter → Standard for the web service only; the worker, cron and previews are
  unchanged.
- Blueprint sync applies the plan on merge and redeploys the service as a normal deploy.
- Specs: `render-deployment` (ADDED requirement "Web service plan").
