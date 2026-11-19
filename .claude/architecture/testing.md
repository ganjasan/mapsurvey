# Testing — full notes

Moved verbatim from `CLAUDE.md` (change `claude-md-diet`).

## Testing

Tests use Django's built-in test framework with PostGIS. Django automatically creates a separate `test_mapsurvey` database.

**Prerequisites**: none — `run_tests.sh` starts the PostGIS and Redis containers itself and waits
for both. Redis is not optional: `settings.py` falls back to `redis://localhost:6379/1` when
`REDIS_URL` is unset, so on a machine running several projects the suite would otherwise connect to
whichever project owns that port and write into its database. `CACHES` sets `IGNORE_EXCEPTIONS`, so
that goes wrong silently rather than failing loudly.

**Full suite**: `./run_tests.sh survey billing api mcp newsletter`. One area: a label
(`survey.tests.test_public_stories`, `survey.tests.test_public_stories.SeedStoryTest`,
`api.tests.test_v1_data`, `billing`).

**Run defaults (change `test-suite-speed`, #272)**: `run_tests.sh` always passes `--noinput`
and runs `--parallel auto` (one worker per core) unless you pass `--parallel` yourself;
`TEST_PARALLEL=1` for `pdb` or a readable traceback order. `KEEPDB=1` adds `--keepdb` — opt-in,
because Django does not re-migrate kept parallel clones, so after a new migration the workers
would test the old schema. `TEST_RUNNER` (`mapsurvey/test_runner.py`) applies to every
`manage.py test`: MD5 password hasher, a temporary `MEDIA_ROOT` (tests never write into
`mediafiles/`), and a Redis database per parallel worker (`1 + worker id`, capped at 14
workers) — django-redis `cache.clear()` is `FLUSHDB`, so a shared database would let one
worker wipe another's rate-limit counters. `tblib` (dev package) is required: without it a
failure inside a worker aborts the whole run with a `TypeError` and a cascade of unrelated
`IntegrityError`s. `pypdf` (dev package) reads the printable-form PDFs back; `reportlab` writes
them (both since change printable-form — a venv from before needs `uv pip install reportlab pypdf`). Views leave `translation.activate()` behind, so the runner resets
the language to `LANGUAGE_CODE` before every test (wrapping `SimpleTestCase._pre_setup`). A test that only passes serially is relying on
another test's state; fix the test, never pin the suite to one process.

**Test location — one module per capability (change `split-survey-tests`, #273)**: the survey
app's tests are the package `survey/tests/`, with `test_<capability>.py` for each folder under
`openspec/specs/` (`-` → `_`) and shared fixtures in `survey/tests/helpers.py`. A change adds its
tests to the module of the capability its spec delta touches; a NEW capability adds its own
module, so parallel branches touch different files. `SpecTestLineageTest`
(`test_test_suite.py`) fails when a module names no spec and is not in `UNMAPPED_MODULES` (with
a reason), or a spec has no module and is not in `SPECS_WITHOUT_SURVEY_TESTS` — both lists may
only shrink, and the stale-entry test enforces it. `api/tests/`, `billing/tests/` and
`mcp/tests/` follow the same one-module-per-capability rule.

**Writing tests**: Use `django.test.TestCase` and GIVEN/WHEN/THEN pattern for docstrings.
