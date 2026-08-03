# Design: web-concurrency

## Context

Production web service (Render, Starter: 0.5 CPU / 512 MB, 1 instance) starts gunicorn
via `Dockerfile` CMD with no concurrency flags → gunicorn defaults → **1 sync worker**,
i.e. one in-flight request for the whole site. `entrypoint.sh` `exec "$@"` passes CMD
through untouched; Render sets no `WEB_CONCURRENCY`; render.yaml has no `dockerCommand`
override. Measured steady state: 143 MB RSS, ~0.2 % CPU — the instance is idle while
requests queue.

Static files are served by WhiteNoise (`CompressedStaticFilesStorage`, non-manifest) →
`Cache-Control: max-age=60`. Cloudflare fronts the site but a 60 s edge TTL means nearly
all asset traffic (Leaflet + css/js, dozens of requests per survey page) falls through to
the same single worker. 30-day metrics: 5 851×304 revalidations, and during the
2026-07-13 classroom incident 170×502 + 89×499 in one hour.

`LOGGING` routes only the `abuse.*` hierarchy to console; with `DEBUG=0`,
`django.request` errors go to the default `mail_admins` handler (ADMINS unset) — 500
tracebacks never reach Render logs (confirmed empty app logs at the 2026-07-27 500s).

Versions: Django 4.2.30, whitenoise 6.11.0, gunicorn 23.0.0, Python 3.9-slim image.

## Goals / Non-Goals

**Goals:**

- ≥8 concurrent request slots on the existing Starter instance, without a plan upgrade.
- Concurrency tunable via env vars — no image rebuild to adjust.
- Static assets cached long-term at browser + Cloudflare edge; asset traffic stops
  consuming gunicorn slots.
- Unhandled-exception tracebacks visible in Render logs.

**Non-Goals:**

- Horizontal scaling / autoscaling (blocked by the persistent media disk; requires the
  S3 migration first — separate change).
- ASGI/async migration.
- Fixing the 2026-07-27 section-submit 500s (needs the logging from this change first),
  the naive `datetime.now` default, or the `debug_toolbar` DEBUG-gate — follow-ups.

## Decisions

### 1. `gthread` worker class, `--workers 2 --threads 4` defaults

`CMD gunicorn --bind :${PORT:-8000} --workers ${WEB_CONCURRENCY:-2} --threads ${GUNICORN_THREADS:-4} --worker-class gthread --timeout ${GUNICORN_TIMEOUT:-60} mapsurvey.wsgi:application`

- **Why gthread**: the workload is I/O-bound (PostGIS queries, static during rollout);
  threads share the ~110 MB Django process, so 8 slots cost ~2 processes (~260 MB total,
  fits 512 MB with headroom) instead of 8 (~900 MB, OOM).
- **Why not more sync workers**: memory-linear; 512 MB caps it at ~3 slots.
- **Why not gevent/eventlet**: extra dependency + monkey-patching risk against GDAL/
  psycopg2 C extensions; not worth it at this scale.
- **Why 2×4 not 1×8**: a second process isolates a crashed/blocked worker; GIL contention
  is irrelevant at 0.5 CPU I/O-bound.
- `--worker-class` stays hardcoded (a topology decision, not a tuning knob); counts and
  timeout are env-tunable. `WEB_CONCURRENCY` is gunicorn's native variable — if Render
  ever starts setting it (Heroku-style), behavior stays coherent.
- `docker-compose.yml` dev command gets the same flags for dev/prod parity.

### 2. Manifest static storage in the non-S3 branch

`STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'`

- Fingerprinted filenames → WhiteNoise emits `Cache-Control: max-age=31536000, immutable`
  for hashed assets automatically; Cloudflare edge and browsers keep them for a year.
  Deploys bust caches by content hash — no stale-asset risk.
- Keep the `STATICFILES_STORAGE` setting name (matches the existing S3 branch idiom;
  supported through Django 4.2 — migrate both branches to `STORAGES` together when
  Django is upgraded).
- Non-hashed entrypoints (`favicon` etc.) keep WhiteNoise's default short TTL — correct,
  they're mutable.
- Manifest storage is strict: `collectstatic` now **fails on dangling references**
  (e.g. `url(missing.png)` in CSS). It runs in `entrypoint.sh` at deploy, so breakage
  surfaces before traffic switches — desirable, but the first deploy may surface
  pre-existing dead references; implementation must run `collectstatic` locally first
  and fix what it finds.

### 3. Root console logger at WARNING

Add a root (`''`) logger with the existing console handler at WARNING, keeping the
`abuse` logger config untouched (`disable_existing_loggers: False` already preserves
Django's defaults; the root logger catches `django.request` ERROR tracebacks and any
other unrouted app errors). Alternative — a dedicated `django.request` entry — rejected:
narrower for no benefit; the root fallback also captures future app loggers.

## Risks / Trade-offs

- [Memory growth under load: 2 workers × 4 threads each holding request state] →
  measured baseline 143 MB total; worst-case ~2×150 MB is within 512 MB. Watch Render
  memory metrics for a week after deploy; `WEB_CONCURRENCY`/`GUNICORN_THREADS` can be
  lowered from the dashboard without a rebuild.
- [DB connections: 8 threads × no `CONN_MAX_AGE` = up to 8 short-lived connections] →
  Render basic-256mb Postgres allows ~100 connections; no risk. (Persistent connections
  are a possible later optimization, not needed now.)
- [First manifest `collectstatic` fails on legacy dead references] → run locally during
  implementation, fix or delete offenders before merging.
- [gthread `--timeout` monitors worker heartbeat, not individual blocked threads] →
  accepted; a fully wedged worker is still killed, per-request timeouts are out of scope.
- [Old cached HTML referencing pre-manifest asset names after deploy] → old
  non-hashed names keep resolving (WhiteNoise serves both original and hashed names);
  no breakage.

## Migration Plan

1. Merge → Render auto-deploys web (worker/cron unaffected: their commands don't use CMD).
2. Deploy-time check: `collectstatic` in entrypoint must pass (manifest strictness).
3. Post-deploy verification: `curl -sI` a fingerprinted asset → `Cache-Control:
   ... immutable`; concurrent smoke test (e.g. 20 parallel requests to a survey page)
   → no 502s; Render memory metric < 350 MB.
4. Rollback: revert commit → Render redeploys previous image; static manifest is
   rebuilt every deploy, so rollback has no persisted state to clean.

## Open Questions

_None — all decisions taken above._
