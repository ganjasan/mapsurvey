# Proposal: db-plan-basic-1gb

## Why

The production database `mapsurvey-db` runs on Render's `basic-256mb`. Its logs show a
Postgres backend `terminated by signal 9: Killed` four times in a week — 2026-09-15 15:23,
09-16 09:11, 09-17 13:20 and 09-21 12:53 UTC. Each kill makes the postmaster restart every
backend: ~2 s of `the database system is in recovery mode`, and every in-flight request
fails with `SSL SYSCALL error: EOF detected` (the `OperationalError` issues in PostHog
error tracking).

Idle RSS is ~100 MB; six-hour samples peaked at 199–242 MB of the 256 MB limit. All four
kills coincided with one creator working in the layer editor on 2–5 MB reference layers
(parallel layer-settings POSTs of 2–4 s plus parallel `layers/<id>.geojson` reads). The web
service is not the constraint: since moving to Standard it idles at 230–280 MB of 2 GB.

## What Changes

- `render.yaml`: `mapsurvey-db` moves to `basic-1gb`; `previewPlan` stays `basic-256mb`.
- The plan is declared in the Blueprint, not the dashboard (same rule as `web-plan-standard`).

## Out of scope

Why a layer-settings save costs that much memory in Postgres — a code change of its own.
A bigger database buys headroom; it does not make the write path cheaper.

## Impact

Render upgrades the instance in place; expect a short database restart while the plan
changes. Merge outside respondent peak hours.
