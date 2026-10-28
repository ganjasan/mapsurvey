## Why

`survey/tests.py` is one 56k-line file with 480 test classes. Every change appends its classes
at the end, so two PRs built in parallel conflict on the same hunk by construction, and nothing
links a spec requirement to the tests that prove it (#273, folding in #237). The OpenSpec backlog
was archived first (#462–#469) so the module names can follow `openspec/specs/`.

## What Changes

- `survey/tests.py` becomes the package `survey/tests/`: one `test_<capability>.py` per
  capability in `openspec/specs/`, plus `test_<area>.py` for the few classes no capability owns
  (listed as unmapped, each with a reason). Classes move byte-for-byte; the only rewrites are the
  ones the move forces: relative imports become `survey.*`, and `__file__`-based paths gain one
  parent level.
- Module-level helpers, constants and fixture classes go to `survey/tests/helpers.py`.
- The five existing `survey/test_*.py` modules move into the package (two renamed to their
  capability: `test_services` → `test_survey_service_layer`, `test_test_runner` →
  `test_test_suite`).
- A guard test (`SpecTestLineageTest`): every `survey/tests/test_*.py` names a spec or is in the
  unmapped allow-list; every spec has a module or is in the allow-list of specs without tests,
  so a new capability cannot land without its module.
- CLAUDE.md, `run_tests.sh` examples and the `customer-story` skill quote the new labels.
- **BREAKING (labels only)**: `survey.tests.FooTest` becomes `survey.tests.test_<cap>.FooTest`;
  `./run_tests.sh survey` still runs everything. Open branches that add classes to
  `survey/tests.py` must move them into the matching module on rebase.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `test-suite`: survey tests are organised one module per capability, enforced by a guard test.

## Impact

`survey/tests.py` (deleted), `survey/tests/` (new), `survey/test_*.py` (moved), CLAUDE.md,
`.claude/skills/customer-story/SKILL.md`. No production code. Test count and pass set identical
before and after.
