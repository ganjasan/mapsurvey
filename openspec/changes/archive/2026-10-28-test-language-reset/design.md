## Decision

`MapsurveyTestRunner.setup_test_environment()` wraps `SimpleTestCase._pre_setup` (a classmethod
Django calls before every test, in the main process and in forked parallel workers alike) so it
calls `translation.deactivate()` — back to `LANGUAGE_CODE` — after the original. The wrapper is
removed in `teardown_test_environment()`.

Alternatives rejected:
- Per-class `translation.override('en')`: the flake moves to the next class that forgot it.
- A custom result class hooking `startTest`: parallel workers use Django's `RemoteTestResult`,
  not the runner's result class, so it would not run there.
- Resetting on `request_finished`: also covers it, but resets mid-test after every client call,
  which a test asserting on the active language would not expect.

`unittest.TestCase` subclasses that are not Django's (`SimpleTestCase` and below) are not
covered; the suite has none that render translations.
