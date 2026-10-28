## ADDED Requirements

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
