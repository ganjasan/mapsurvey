## Context

The sync command is idempotent (`posthog.set` replaces current state; first touch goes through
`set_once`) and fails with `CommandError` when `POSTHOG_PROJECT_KEY` is unset. Production already
has one daily Render cron, `mapsurvey-preview-media-reclaim` (04:30 UTC), whose `reclaim.sh` runs
the media reclamation and `notify_lapsed`. Celery has no beat schedule.

## Goals / Non-Goals

**Goals:** labels reach PostHog within a day of being written, whatever wrote them.

**Non-Goals:** real-time sync on save (a `UserCohort` signal would miss raw-SQL writes, which are
how the GTM review labels creators); renaming the cron (a rename creates a new Render service).

## Decisions

- **Last step of `reclaim.sh`, not a new cron service.** One Blueprint block instead of two, no
  added cost, same image and database. Alternative — a dedicated `mapsurvey-posthog-person-sync`
  cron — gives a clearer name and an independent failure status, at the price of another service
  to configure; not worth it for a seconds-long step.
- **After `notify_lapsed`.** `set -e` stops the script at the first failure; putting the sync last
  means a PostHog problem (or the key not yet set) can never block reclamation or lapse mail. A
  failed sync still marks the run failed in Render, which is the signal we want.
- **Daily is enough.** The scanners spend free credits only; a day's delay costs a handful of
  observations.

## Risks / Trade-offs

- [The key is not set on the cron after deploy] → every run ends with `CommandError` and shows as
  failed in Render; the earlier steps have already finished. Set both variables in the dashboard
  as part of the rollout.
- [The cron's name no longer describes everything it does] → the header comment in `reclaim.sh`
  lists its steps.

## Migration Plan

Merge → set `POSTHOG_PROJECT_KEY` and `POSTHOG_API_HOST` on the cron in the Render dashboard (same
values as the web service) → check the next run's log for `updated N people`. Rollback: remove the
line from `reclaim.sh`.
