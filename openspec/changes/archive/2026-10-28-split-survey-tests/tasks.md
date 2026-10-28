## 1. Mapping

- [x] 1.1 Blame-based capability candidates per class; four parallel reading passes against the spec catalog; merge and review (unmapped and low-confidence by hand)
- [x] 1.2 Final map: every class → a capability in `openspec/specs/` or `unmapped:<area>` with a reason

## 2. Split

- [x] 2.1 Baseline: verbose serial run of `survey`, sorted `(class, method)` ids and FAIL/ERROR set
- [x] 2.2 Generate `survey/tests/` (modules, `helpers.py`, `__init__.py`); move the five `survey/test_*.py` modules in; delete `survey/tests.py`
- [x] 2.3 pyflakes over the package: no undefined names
- [x] 2.4 After-run: identical `(class, method)` ids and FAIL/ERROR set

## 3. Guard

- [x] 3.1 `SpecTestLineageTest` in `survey/tests/test_test_suite.py` with `UNMAPPED_MODULES` (reasons) and `SPECS_WITHOUT_SURVEY_TESTS`; GIVEN/WHEN/THEN docstrings
- [x] 3.2 Guard fails on a fake unknown module and on a fake spec without a module (two unit tests on synthetic inputs, plus a stale-entry test)

## 4. Docs

- [x] 4.1 CLAUDE.md: test location, per-capability rule, new label examples
- [x] 4.2 `.claude/skills/customer-story/SKILL.md` and `openspec/specs/test-suite` labels
- [x] 4.3 PR text: what every open branch must do on rebase
