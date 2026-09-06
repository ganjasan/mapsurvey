# Tasks — fix-new-question-modal-layout

## 1. Code

- [x] 1.1 `question_form_modal.html`: create-mode CSS hides only what sits below the
      type picker + the Create button; title "New Question"
- [x] 1.2 Type-pick POST sends `name` and `subtext` along with `draft=1`
- [x] 1.3 `editor_question_create` draft path stores them (`subtext` via
      `coerce_creator_html`)

## 2. Tests

- [x] 2.1 Update the picker-only assertions; add GIVEN/WHEN/THEN test for name/subtext
      carried on pick and no draft marker when named
- [x] 2.2 Baseline + after-changes run of the question modal tests

## 3. Ship

- [x] 3.1 Offer commit / push / PR
