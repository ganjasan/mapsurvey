## Context

`survey/tests.py`: 56 275 lines, 490 top-level classes (480 with tests, 10 fixtures/fakes),
22 module-level helper functions, 8 constants, 85 imports (some in the middle of the file).
Five more modules already sit beside it (`survey/test_*.py`). No test class subclasses another
test-bearing class, and no top-level name is bound twice to different objects, so classes can be
moved independently without duplicating or shadowing anything.

## Decisions

### 1. Mapping classes to capabilities

Two signals, then a judgement per class:
- `git blame` of each `class X(` line → the introducing commit → the `specs/<cap>/` folders that
  commit touched. One capability for 136 classes; several for 237 (multi-spec PRs); none for 117
  (pre-OpenSpec history).
- A reading of each class (name, docstring, test names) against the spec catalog (capability
  names, purposes, requirement titles), done in four parallel passes and reviewed.

`survey-editor` is the default only for editor behaviour no narrower spec covers. Classes no
capability owns go to `test_<area>.py` and are listed in the guard's allow-list with a reason —
each is either a missing spec or a class to fold into one later.

### 2. Mechanical move, generated

A script (kept out of the repo; the result is reviewed instead) copies every class's source
byte-for-byte, together with the comment lines above it, in original order. Each module imports
only the names its classes use, rebuilt from the original import statements. Helpers go to
`helpers.py`, imported by name. Two rewrites are forced by the move one directory down:
`from .x` → `from survey.x`, and `__file__`-based paths gain one parent level. Where a capability
already had a module (`test_question_groups`, `test_translation_table`, …), moved classes are
appended under a marker, and the generator refuses to run if the appended imports would rebind a
name the module already defines.

### 3. Proof of equivalence

Before and after: the sorted list of `(class, test method)` ids from a verbose run, and the
pass/fail set, must be identical. Module paths change, class and method names do not. pyflakes
over the package must report no undefined names.

### 4. Guard

`SpecTestLineageTest` in `test_test_suite.py`: modules ↔ `openspec/specs/` folders, with two
allow-lists (`UNMAPPED_MODULES` with reasons; `SPECS_WITHOUT_SURVEY_TESTS` — capabilities
tested elsewhere (`api/`, `billing/`, `mcp/`) or by nothing yet). The second list is the
"requirements without tests" report #237 asked for, at capability granularity; it may only
shrink. Requirement-level `Spec:` tags are left for later changes to add gradually.

## Risks / Trade-offs

- **Every open branch that appends to `survey/tests.py` conflicts once.** → The fix is the same
  each time: move the new classes into the matching module. Announced in the PR.
- **A wrong capability for a class.** → Cheap to fix later (move a class between modules); the
  guard does not judge content.
- **Parallel runs reorder classes**: modules change which worker runs what. → The language
  reset from #461 removes the known order dependency; any other surfaces as a before/after
  difference and is fixed in the test.
