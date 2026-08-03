# Proposal: web-concurrency

## Why

Production runs gunicorn with its defaults — **one sync worker** — so the whole of
mapsurvey.org handles exactly one HTTP request at a time. On 2026-07-13 ~02:00 UTC a
university lecturer (ENME215, user 318) sent ~45+ students to a one-question point survey
during a lecture; the single worker queued up, Render's proxy returned 170×502, students
gave up (89×499), only 4 of 45 sessions saved an answer and 0 finished. The lecturer
emailed us about it. WhiteNoise's non-manifest storage (`max-age=60`) amplifies the
problem: every static asset re-validates through the same single worker every minute
(5 851×304 in 30 days), and Cloudflare's edge cache is effectively useless at that TTL.
Meanwhile the instance idles at 0.2 % CPU and 143/512 MB — capacity is there, concurrency
is not. A second blind spot surfaced during diagnosis: unhandled 500s log nothing to
Render (LOGGING covers only `abuse.*`; `django.request` goes to mail_admins), so
production tracebacks are invisible.

## What Changes

- Gunicorn start command gains explicit concurrency: `gthread` worker class with
  multiple workers and threads (target ≥8 concurrent request slots), configurable via
  environment variables so tuning needs no image rebuild.
- Static files storage switches to WhiteNoise's manifest storage
  (`CompressedManifestStaticFilesStorage`) with far-future `Cache-Control`, so
  fingerprinted assets are cached by browsers and Cloudflare's edge instead of hitting
  gunicorn.
- `LOGGING` gains a `django.request` (and root fallback) console handler so 500
  tracebacks appear in Render logs.

Out of scope (noted during diagnosis, separate follow-ups): naive
`datetime.now` default on `SurveySession.start_datetime`; `debug_toolbar` not gated by
`DEBUG`; the 2026-07-27 POST-section 500s (diagnosable once logging lands).

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `render-deployment`: "Web service configuration" — start command must specify worker
  class/count/threads (env-tunable) instead of gunicorn defaults; "Static files serving" —
  manifest storage with immutable long-lived cache headers; new requirement for
  production error logging to stdout.

## Impact

- `Dockerfile` — CMD gains worker/thread flags driven by env vars.
- `render.yaml` — env vars for gunicorn tuning (defaults keep dev behavior unchanged).
- `mapsurvey/settings.py` — `STATICFILES_STORAGE` (non-S3 branch), `LOGGING`.
- Memory: +~110 MB for the second worker; fits the 512 MB Starter instance (measured
  143 MB steady with one worker). No Render plan change.
- Manifest storage makes `collectstatic` fail on broken static references — surfaces
  at deploy time in `entrypoint.sh`, not at runtime (this is desirable but may catch
  pre-existing dead references on first deploy).
