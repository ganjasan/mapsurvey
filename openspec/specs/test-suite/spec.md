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

### Requirement: Every test starts in the default language
The project test runner SHALL make the default language (`LANGUAGE_CODE`) the active one before
each test, so a language activated by an earlier test in the same process cannot change what a
later test reads.

#### Scenario: Earlier test left another language active
- **WHEN** a test activates Portuguese and does not reset it, and the next test in the same
  process renders a translatable label without making a request
- **THEN** the label is in the default language

### Requirement: Survey tests live in one module per capability
The `survey` app's tests SHALL live in the package `survey/tests/`, with the tests that prove a capability's requirements in `survey/tests/test_<capability>.py`, where `<capability>` is the folder name under `openspec/specs/` with `-` written as `_`. Shared fixtures and helpers SHALL live in `survey/tests/helpers.py`. A test class that no capability owns SHALL live in a `test_<area>.py` module that is listed, with a reason, in the guard's unmapped allow-list.

#### Scenario: A change adds tests for an existing capability
- **WHEN** a change adds tests proving a requirement of the `public-stories` capability
- **THEN** they are added to `survey/tests/test_public_stories.py`

#### Scenario: Running one capability's tests
- **WHEN** `./run_tests.sh survey.tests.test_public_stories` is started
- **THEN** only that capability's tests run

#### Scenario: Running everything
- **WHEN** `./run_tests.sh survey` is started
- **THEN** every module in `survey/tests/` runs

### Requirement: A guard keeps specs and test modules in step
A test SHALL fail when a `survey/tests/test_*.py` module names neither a folder under `openspec/specs/` nor an entry of the unmapped allow-list, and when a folder under `openspec/specs/` has no test module and is not in the allow-list of specs without survey tests.

#### Scenario: A new capability lands without tests
- **WHEN** a change archives a new spec folder `openspec/specs/foo-bar/` and adds no `survey/tests/test_foo_bar.py`
- **THEN** the guard test fails and names `foo-bar`

#### Scenario: A module named after no spec
- **WHEN** someone adds `survey/tests/test_misc_stuff.py` without an allow-list entry
- **THEN** the guard test fails and names the module

