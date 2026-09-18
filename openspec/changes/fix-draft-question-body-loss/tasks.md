# Tasks — fix-draft-question-body-loss

## 1. Code
- [x] 1.1 `survey_detail.html`: the close handler keeps a draft whose `subtext` input has content
- [x] 1.2 `editor_question_delete`: `configured` counts subtext with tags stripped
- [x] 1.3 `hide.bs.modal`: closing create mode with typed Name/Subtext saves it as a `text` question

## 2. Tests
- [x] 2.1 GIVEN/WHEN/THEN test: `if_empty` POST on a subtext-only question returns 204 and keeps the row
- [x] 2.2 GIVEN/WHEN/THEN test: `if_empty` POST on a question whose subtext is `<p><br></p>` deletes it
- [x] 2.3 Baseline + after-changes run of the editor question tests
- [x] 2.4 Playwright: Formatted Text body survives close; untouched draft still discarded
- [x] 2.5 Playwright: close before a type pick keeps the text as a `text` question; untouched modal creates nothing

## 3. Ship
- [ ] 3.1 Offer commit / push / PR
