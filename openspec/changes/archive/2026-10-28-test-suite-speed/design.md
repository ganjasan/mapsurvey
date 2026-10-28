## Context

`run_tests.sh` starts this worktree's PostGIS and Redis (ports from `PORT_OFFSET`) and calls
`manage.py test "$@"` with the production settings module. There is no test settings module, no
custom runner, no CI — the suite is run by hand or by an agent, on a 4-core / 19 GB laptop that
usually has several worktrees' stacks up.

Measured before the change (2026-10-28, `survey billing api`, master `f4239c6`): see
"Measurements" below.

## Goals / Non-Goals

**Goals**
- Full run of `survey billing api` well under the current wall time, target ≤ 3–4 min on this
  machine.
- `run_tests.sh` never blocks on input.
- Identical pass/fail set before and after (no test edited to make it pass).

**Non-Goals**
- Splitting `survey/tests.py` (#273), tagging fast/slow tiers, rewriting fixtures.
- CI.

## Decisions

### 1. Test-only settings live in a runner, not in `settings.py` branches

`mapsurvey/test_runner.py::MapsurveyTestRunner(DiscoverRunner)`, set as `TEST_RUNNER`. In
`setup_test_environment()` it enables an `override_settings` for `PASSWORD_HASHERS` (MD5) and
`MEDIA_ROOT` (a `tempfile.mkdtemp()` removed in `teardown_test_environment()`).

Why a runner: `override_settings` sends `setting_changed`, which clears the `get_hashers` cache and
storage instances — assigning `settings.X` in a `'test' in sys.argv` branch would not, and would
also leak into `manage.py shell` sessions named "test…". It applies to any `manage.py test`,
including the e2e script, without each script repeating it. Forked parallel workers inherit it.

Alternative rejected: a `mapsurvey/settings_test.py` with `DJANGO_SETTINGS_MODULE` in
`run_tests.sh` — a plain `manage.py test` (what agents often run) would silently skip it.

MD5 is safe here: no test asserts the algorithm prefix; `SurveyHeader.check_password` round-trips
through `make_password`/`check_password` and is hasher-agnostic.

### 2. A Redis database per parallel worker

`CACHES` points at Redis DB 1. Under `--parallel`, workers are forked processes sharing it, and
tests call `cache.clear()` (django-redis: `FLUSHDB`) — one worker's clear would erase another's
ratelimit counters and `LastActivityMiddleware` throttle keys mid-test.

The runner's `parallel_test_suite` is a `ParallelTestSuite` subclass whose `init_worker` calls
Django's and then points the default cache at DB `1 + worker_id` (worker ids start at 1) via
`override_settings(CACHES=…)` — the signal resets `caches`, so the next `cache` access connects to
the worker's DB. Redis has 16 DBs, which caps the useful parallelism at 14; the runner clamps
`--parallel` to that.

Celery uses DB 0 and tests never reach a broker (`_eager_import`, mocked `.delay`), so it needs no
isolation.

### 3. `run_tests.sh` defaults

- `--noinput` always (the old hang: a leftover `test_mapsurvey` → interactive "Type 'yes'").
- `--parallel ${TEST_PARALLEL:-auto}` unless the caller passed `--parallel` themselves.
  `auto` = CPU count (4 here). A single class (`survey.tests.SmokeTest`) is not split across
  workers by Django anyway — `TEST_PARALLEL=1` exists for debugging with `pdb`.
- `--keepdb` only with `KEEPDB=1`. Django's PostgreSQL backend skips re-cloning an existing
  `test_mapsurvey_N` under `--keepdb`, while it does migrate the main test DB — after a branch adds
  a migration, workers would run on the old schema. Fresh DB creation is measured below; if it is
  a minor share of the run, opt-in is the honest default.

### 4. Measuring

`--durations 60` (Django ≥ 5.0) before and after, plus wall time from `/usr/bin/time`. Results
recorded here; the pass/fail set compared as sorted `FAIL:`/`ERROR:` lines.

## Risks / Trade-offs

- **Hidden inter-test coupling surfaces under `--parallel`** (shared files, order-dependent
  state). → Compare failure sets; any new failure is investigated, fixed in the test only if the
  test was relying on order, never by marking it skip. Classes that cannot run concurrently get
  `serialized_rollback`/a documented fix, not a global `--parallel 1`.
- **Memory**: 4 workers × Django + GDAL. → Watched during the after-run; 7 GB free is ample for
  ~4 × 300 MB.
- **Four clones of the test DB** take extra PostGIS time on setup. → Part of the measured wall
  time.
- **`--durations` and `--parallel`** both work on Django 5.2; durations are reported per worker
  and merged.

## Measurements

| Run | Wall time | Tests | Failures/errors |
|---|---|---|---|
| Baseline (serial, PBKDF2) | 1991 s (33 min) | 3260 | 0 |
| + MD5 hasher (`TEST_PARALLEL=1`) | 377 s (6.3 min) | 3266 | 0 |
| + `--parallel auto` (4 workers), same labels | 252 s | 3266 | 0 after the `CsvTest` fix |
| Full set `survey billing api mcp newsletter`, defaults | 285 s (4.8 min) | 3366 | 0 |

Baseline's slowest tests were the `Comment*` classes at 3–8 s each: their `setUp` creates and
logs in several users, and Django 5.2's PBKDF2 runs 1 000 000 iterations per hash.

What the first parallel run surfaced:

- **`tblib` was missing.** Without it a worker cannot serialise a failure's traceback back to the
  main process, the pool raises a `TypeError`, and the whole run aborts after the first failure —
  the `IntegrityError` / `connection already closed` noise in that run was the aftermath, not real
  failures. `tblib` is now a dev package (Pipfile + lock, nothing else in the lock moved).
- **Order-dependent language.** Views call `translation.activate()` and nothing resets it after
  a test-client request, so the process keeps the last respondent's language. `CsvTest` calls the
  exporter directly and reads labels in whatever language is active; serially the class happened
  to follow English tests. Fixed in the test (`translation.override('en')` in `setUp`); the
  exporter's behaviour (labels in the creator's UI language) is right.

## Migration Plan

Merge = new defaults for everyone. Rollback: `TEST_PARALLEL=1 ./run_tests.sh …` per run, or
revert the PR. No data, no deploy impact (`TEST_RUNNER` is read only by `manage.py test`).
