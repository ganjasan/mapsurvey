# Tasks: fix-malformed-archive-import

## 1. Safe field reads

- [x] 1.1 `_archive_text()` — an explicit `null` reads as an absent key, then slices safely
- [x] 1.2 Apply to `redirect_url`, `section.title`, `section.code`, `question.color`, `question.icon_class`
- [x] 1.3 `_required_text()` for `survey.name`, `section.name`, `question.code` — `ImportError` naming the element instead of a bare `KeyError`

## 2. The durable part

- [x] 2.1 Wrap the import so `TypeError`/`KeyError`/`IndexError`/`AttributeError`/`ValueError` become `ImportError` with the original type and message — the next hand-edited archive will null something this PR did not touch
- [x] 2.2 `logger.exception` first, so a genuine bug behind a shape error still leaves a traceback in the request log
- [x] 2.3 Re-raise `ImportError` untouched so the specific messages above are not swallowed by the catch-all

## 3. Tests

- [x] 3.1 Baseline: a well-formed archive still imports — otherwise the null cases could pass for the wrong reason
- [x] 3.2 `"redirect_url": null` — the exact payload that produced the reported 500
- [x] 3.3 Nulls across section and question optional fields
- [x] 3.4 Missing required field → `ImportError` naming it
- [x] 3.5 Wrongly typed field → `ImportError`, and explicitly fail the test on any other exception type
- [x] 3.6 The view returns a message rather than a 500
- [x] 3.7 Confirm the tests fail without the fix — 4 of 6 error out, reproducing `TypeError: 'NoneType' object is not subscriptable` and `KeyError: 'name'`

## 4. Verification

- [x] 4.1 `./run_tests.sh survey` — compare against the 1772-test / OK baseline
- [x] 4.2 Mark PostHog `01a036e2` (`SurveySection.DoesNotExist`) resolved — already fixed by `f94e9cc`, no code needed
- [ ] 4.3 After merge + deploy, mark PostHog `01a02d72` resolved
