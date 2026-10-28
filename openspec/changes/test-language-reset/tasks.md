## 1. Runner

- [x] 1.1 Wrap `SimpleTestCase._pre_setup` in `MapsurveyTestRunner` to `translation.deactivate()` before each test; restore on teardown
- [x] 1.2 Test (GIVEN/WHEN/THEN) in `survey/test_test_runner.py`: a language left active is gone in the next test (fails under Django's stock runner, passes under ours)
- [x] 1.3 CLAUDE.md "Testing": replace the "set its language itself" note
- [x] 1.4 `api/v1/responses.py::_write_ins` orders rows by `pk`, so "first written" is deterministic

## 2. Verify

- [x] 2.1 Full `./run_tests.sh survey billing api mcp newsletter` green, twice in a row
