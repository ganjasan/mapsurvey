# Tasks: web-concurrency

## 1. Gunicorn concurrency

- [x] 1.1 Update `Dockerfile` CMD: `--workers ${WEB_CONCURRENCY:-2} --threads ${GUNICORN_THREADS:-4} --worker-class gthread --timeout ${GUNICORN_TIMEOUT:-60}` (keep `--bind :${PORT:-8000}`)
- [x] 1.2 Update `docker-compose.yml` web command with the same flags (dev/prod parity)
- [x] 1.3 Declare `WEB_CONCURRENCY`, `GUNICORN_THREADS`, `GUNICORN_TIMEOUT` in `render.yaml` web service envVars with explicit default values (visibility + dashboard tunability)

## 2. Manifest static storage

- [x] 2.1 Switch non-S3 branch in `mapsurvey/settings.py` to `whitenoise.storage.CompressedManifestStaticFilesStorage`
- [x] 2.2 Run `collectstatic` locally against the manifest storage; fix or remove any dangling static references it surfaces — found one: stripped the `sourceMappingURL` comment from `survey/assets/js/bootstrap.min.js` (the `.map` file was never vendored)
- [x] 2.3 Verify a hashed asset gets far-future immutable caching (local gunicorn, `curl -sI`) — `max-age=315360000, public, immutable` on `css/main.<hash>.css`; non-hashed entrypoints keep `max-age=60` as intended
- [x] 2.4 Verify every `{% static %}` literal in templates resolves in the manifest (manifest storage raises at render time on a miss, and collectstatic does not check templates) — 203/203 resolve

## 2b. Persistent DB connections (added after load testing)

- [x] 2b.1 `CONN_MAX_AGE=300` + `CONN_HEALTH_CHECKS` in both DATABASES branches, env-tunable via `DB_CONN_MAX_AGE` — without it the concurrency fix measurably regressed p95 (see 5.6)

## 3. Production error logging

- [x] 3.1 Add root (`''`) logger with console handler at WARNING to `LOGGING` in `mapsurvey/settings.py`, preserving the `abuse` logger block
- [x] 3.2 Verify: simulated `django.request` ERROR with `DEBUG=0` emits a full traceback on stdout; `abuse.*` records still formatted as before

## 4. Test suite

- [x] 4.1 Test suite run: `./run_tests.sh survey --noinput` — 853 tests, 2 errors, both pre-existing and environmental (`LastActivityMiddlewareTest` needs Redis on `localhost:6379`, which `run_tests.sh` does not start); both pass with Redis up. Unrelated to this change.
- [x] 4.2 Document the Redis test dependency in `CLAUDE.md`

## 5. Load test (k6)

- [x] 5.1 Add `survey/management/commands/seed_loadtest_survey.py` — idempotent published single-`point` survey, so a Render preview's empty DB has identical content for both runs
- [x] 5.2 Add `loadtest/lecture-burst.js` — ramping VUs model students arriving off a lecture slide; each loads the section page, batches the 8 same-origin assets (Leaflet/Bootstrap/jQuery/htmx are CDN-hosted and never hit us), pauses, then submits a point. Thresholds: zero 5xx, page p95 < 3 s, >99 % submits accepted
- [x] 5.3 Add `loadtest/README.md` + `CLAUDE.md` section — including why this cannot be validated on localhost and the never-against-production rule
- [x] 5.4 PR #47 preview + `loadtest-baseline` (PR #48) preview seeded via one-off Render API jobs (SSH keys not registered in the Render account)
- [x] 5.5 Baseline run: p95 7 435 ms, 1 239 requests — fails the 3 s threshold. At single-IP scale the failure mode is latency, not 5xx (Render's proxy queues patiently); the 502 storm needs a real crowd
- [x] 5.6 Fixed run: p95 502 ms, 2 401 requests, 0 5xx, 100 % submits — all thresholds pass. Required a second fix discovered by the harness: workers alone regressed p95 to 12 107 ms (per-request Postgres connection forks pegged the 0.1-vCPU DB) until `CONN_MAX_AGE` landed
- [x] 5.7 Memory 214–230 MB of 512 during the heaviest (invalid 50-VU) run — comfortable headroom

## 6. Follow-ups to file separately (out of scope here)

- [ ] 6.1 `LastActivityMiddleware._touch()` fails toward silence, not correctness: with `IGNORE_EXCEPTIONS: True`, django-redis returns `None` instead of raising when Redis is down, so `if not cache.add(...)` takes the early return and the activity write is skipped — the opposite of what its comment promises
- [ ] 6.2 `SurveySession.start_datetime` uses `default=datetime.now` (naive) — emits `RuntimeWarning` in production, should be `timezone.now`
- [ ] 6.3 `debug_toolbar` app + middleware are unconditionally installed, not gated on `DEBUG`
- [ ] 6.4 Diagnose the 2026-07-27 `POST /surveys/<uuid>/section_3/` 500s — now possible once 3.1 ships and tracebacks reach Render logs
