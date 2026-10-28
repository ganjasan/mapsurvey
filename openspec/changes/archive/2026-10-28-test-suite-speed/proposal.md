## Why

The full suite (`survey`, `billing`, `api`) takes well over ten minutes on a dev machine, so
changes ship after a partial run or a run left in the background and never read (#272). Most of
the time is not the code under test: every `create_user` + `client.login` pays for PBKDF2 (~350
`setUp` methods create users, only one class uses `setUpTestData`), the run is single-process on a
four-core machine, and a leftover `test_mapsurvey` database makes the next run hang on an
interactive prompt with no output.

## What Changes

- A project test runner (`TEST_RUNNER`) that applies test-only settings for every `manage.py test`
  run, whatever script started it:
  - a fast password hasher (MD5) — tests never depend on the hash algorithm;
  - a throw-away `MEDIA_ROOT` per run, so tests stop writing into the checkout's `mediafiles/`
    and parallel workers never delete each other's files;
  - under `--parallel`, a Redis database per worker, because django-redis `cache.clear()` is a
    `FLUSHDB` and one worker's clear would wipe another's rate-limit and activity keys.
- `run_tests.sh` always passes `--noinput` (no more silent hang on a leftover test DB) and runs
  with `--parallel` by default; `TEST_PARALLEL=1` (or any number) overrides it, and explicit
  arguments still win.
- `--keepdb` stays opt-in (`KEEPDB=1`): Django does not re-migrate kept parallel clones, so a
  default `--keepdb` would run tests against a stale schema after a migration lands.
- `tblib` as a dev package: without it a failure inside a parallel worker aborts the whole run.
- `CsvTest` (translation table) sets its UI language itself instead of inheriting whatever an
  earlier test left active — the one order dependency the parallel run surfaced.
- CLAUDE.md documents the new defaults, the knobs, and how to run one area.
- Before/after timings recorded in the design.

Not in this change: splitting `survey/tests.py` (#273) and moving fixtures to `setUpTestData`
(follow-ups once the per-class timing shows where it pays).

## Capabilities

### New Capabilities
- `test-suite`: how the project's automated tests are run — non-interactive, isolated per run and
  per parallel worker, with test-only speed settings applied by the runner.

### Modified Capabilities
<!-- none -->

## Impact

- New `mapsurvey/test_runner.py`; `TEST_RUNNER` in `mapsurvey/settings.py`.
- `run_tests.sh` argument defaults.
- CLAUDE.md "Testing" section (drops the stale "run_tests.sh does not start Redis" paragraph).
- No production code path changes; no migrations; one dev-only dependency (`tblib`).
- Every open branch keeps working: test labels are unchanged.
