# Tasks — fix-publish-fetch-silent-failure

## 1. Fix

- [x] 1.1 Add a shared `publishFetchFailed()` handler with a `{% trans %}` message in
      `survey/templates/editor/partials/_lifecycle_scripts.html`
- [x] 1.2 `checkAndPublishDraft`: guard `r.ok` before `r.json()` (non-OK → throw) and attach
      `.catch(publishFetchFailed)`
- [x] 1.3 `doPublishDraft`: attach `.catch(publishFetchFailed)` to both fetch chains, keeping
      the existing status-specific `alert()` paths unchanged — plus `postTransition`
      (the testing→published publish path), found equally silent while implementing

## 2. Test

- [x] 2.1 Guard test in `survey/tests.py`: owner opens survey detail for a survey with a
      draft, page contains the failure handler and `.catch` wiring on the publish chains
      (`EditorVersioningEndpointsTest.test_publish_chains_carry_network_failure_handler`)

## 3. Verify

- [x] 3.1 Run the survey test suite (`./run_tests.sh survey`) — no new failures
- [ ] 3.2 Manual: block `check-compatibility/` in DevTools, click Publish draft, see the
      message (dev server)
