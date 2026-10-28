## 1. Baseline

- [x] 1.1 Full run `survey billing api --noinput --durations 60` on master before any change; record wall time, test count, sorted FAIL/ERROR list and the slowest tests in design.md

## 2. Runner

- [x] 2.1 `mapsurvey/test_runner.py`: `MapsurveyTestRunner(DiscoverRunner)` enabling `override_settings(PASSWORD_HASHERS=[MD5], MEDIA_ROOT=<mkdtemp>)` in `setup_test_environment`, disabling it and removing the dir in `teardown_test_environment`
- [x] 2.2 `ParallelTestSuite` subclass whose `init_worker` points the default cache at Redis DB `1 + worker_id`; runner clamps `parallel` to the available Redis DBs
- [x] 2.3 `TEST_RUNNER = 'mapsurvey.test_runner.MapsurveyTestRunner'` in settings
- [x] 2.4 Tests (GIVEN/WHEN/THEN) in `survey/test_test_runner.py`: hasher is the fast one under test; MEDIA_ROOT is a temp dir outside the checkout; distinct cache DB per worker and a clear in one keeps the other; parallel clamp
- [x] 2.5 `tblib` in Pipfile `[dev-packages]` + lock (parallel workers cannot report a failure without it)

## 3. run_tests.sh

- [x] 3.1 Always `--noinput`
- [x] 3.2 `--parallel ${TEST_PARALLEL:-auto}` unless `--parallel` is among the arguments
- [x] 3.3 `--keepdb` only with `KEEPDB=1`

## 4. Measure and compare

- [x] 4.1 Run with MD5 only (`TEST_PARALLEL=1`): wall time, failure set == baseline
- [x] 4.2 Run with defaults (parallel): wall time, failure set == baseline; investigate any difference (`CsvTest` language dependency fixed in the test)
- [x] 4.3 Fill the Measurements table in design.md; fresh DB setup + 4 clones is ~20 s of 285 s, so `KEEPDB` stays opt-in

## 5. Docs

- [x] 5.1 CLAUDE.md "Testing": defaults, `TEST_PARALLEL`, `KEEPDB`, one-area runs; drop the stale "run_tests.sh does not start Redis" paragraph
- [x] 5.2 Comment on #272 with the before/after numbers
