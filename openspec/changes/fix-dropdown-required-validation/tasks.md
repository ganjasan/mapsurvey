# Tasks: fix-dropdown-required-validation

## 1. Fix

- [x] 1.1 `choice_dropdown.html`: blank placeholder option in the hidden `<select>`,
      selected when no option is; keep it out of the visible `<ul>`.
- [x] 1.2 `survey/views.py`: drop empty values before the answer-storage branch, so an
      optional dropdown left alone stores nothing.

## 2. Tests

- [x] 2.1 Markup: placeholder present and selected with no stored answer; not selected
      when an answer exists; absent from the visible list.
- [x] 2.2 Storage: POST without the value stores no answer; POST with a code stores it
      unchanged (regression guard for the original feature).
- [x] 2.3 Full `./run_tests.sh survey`.

## 3. Manual verification

- [x] 3.1 Dev stand in a browser: forward button on an untouched required dropdown shows
      the required summary and does not advance; picking an option advances and stores
      the right code; optional dropdown left empty advances and stores nothing.

## 4. Ship

- [ ] 4.1 PR referencing this change.
- [ ] 4.2 After deploy: re-check the live Olney demo, and clean the phantom `[1]` answers
      from its demo sessions.
