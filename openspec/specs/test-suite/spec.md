# test-suite Specification

## Purpose
How the project's automated tests are run: non-interactively, in parallel by default, isolated
per run (media) and per worker (cache), with test-only speed settings applied by the project test
runner for every `manage.py test`. Created by change `test-suite-speed` (#272).

## Requirements
### Requirement: Test runs never wait for input
`run_tests.sh` SHALL run Django's test command non-interactively, so a leftover test database is
replaced instead of prompting.

#### Scenario: Leftover test database
- **WHEN** a previous run left `test_mapsurvey` behind and `./run_tests.sh survey` is started
- **THEN** the run drops and recreates the test database without asking and proceeds to the tests

### Requirement: Test-only speed settings apply to every test run
The project test runner SHALL apply a fast password hasher for the duration of any
`manage.py test` run, whether it was started by `run_tests.sh` or directly, and SHALL leave
settings unchanged outside test runs.

#### Scenario: Password hashing in tests
- **WHEN** a test creates a user with a password under `manage.py test`
- **THEN** the stored hash uses the fast test hasher, and logging in with that password succeeds

#### Scenario: Outside test runs
- **WHEN** the application runs under `runserver`, gunicorn or `manage.py shell`
- **THEN** the production password hashers are in effect

### Requirement: Test runs do not write into the checkout's media directory
Each test run SHALL store files written through the default storage in a temporary directory
that is removed when the run ends.

#### Scenario: Upload during a test
- **WHEN** a test saves a file through the default storage
- **THEN** the file is written under the run's temporary media directory, not under the checkout's
  `mediafiles/`, and the directory is gone after the run

### Requirement: The suite runs in parallel by default
`run_tests.sh` SHALL run tests in parallel worker processes by default, SHALL let the caller set
the worker count (`TEST_PARALLEL`, or an explicit `--parallel` argument which takes precedence),
and SHALL produce the same pass/fail result as a serial run.

#### Scenario: Default run
- **WHEN** `./run_tests.sh survey billing api` is started with no parallel setting
- **THEN** tests run across as many workers as the machine has CPUs

#### Scenario: Serial run for debugging
- **WHEN** `TEST_PARALLEL=1 ./run_tests.sh survey.tests.test_smoke` is started
- **THEN** tests run in a single process

### Requirement: Parallel workers do not share cache state
Each parallel worker SHALL use its own Redis cache database, so clearing the cache in one worker
cannot change cache state another worker's test depends on.

#### Scenario: One worker clears the cache
- **WHEN** a test in worker 1 calls `cache.clear()` while a test in worker 2 holds a rate-limit
  counter in the cache
- **THEN** worker 2's counter is unaffected

#### Scenario: More workers than cache databases
- **WHEN** a parallel run asks for more workers than there are free Redis databases
- **THEN** the runner caps the worker count at the number of available databases

### Requirement: Keeping the test database is opt-in
`run_tests.sh` SHALL create a fresh test database by default and SHALL keep it between runs only
when the caller opts in (`KEEPDB=1`).

#### Scenario: Default
- **WHEN** `./run_tests.sh survey` is started without `KEEPDB`
- **THEN** the test databases are created fresh and destroyed after the run

#### Scenario: Opt-in
- **WHEN** `KEEPDB=1 ./run_tests.sh survey` is started
- **THEN** the run reuses the existing test database

