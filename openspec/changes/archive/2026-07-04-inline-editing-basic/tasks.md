## 1. Backend

- [ ] 1.1 Add `analytics_answer_edit` POST endpoint: session_id + question_id, sets value by type (text, number, choice, multichoice)
- [ ] 1.2 Add URL pattern
- [ ] 1.3 Handle create-if-not-exists (for previously blank cells)

## 2. Table inline editing

- [ ] 2.1 Double-click on question cell → replaces with input (text/number) or select (choice)
- [ ] 2.2 On blur/Enter → POST to save, update cell display
- [ ] 2.3 Pass question choices as data attributes for choice columns
- [ ] 2.4 JS functions: `startCellEdit()`, `saveCellEdit()`, `cancelCellEdit()`

## 3. Session detail modal editing

- [ ] 3.1 Add edit icon per answer row in session detail
- [ ] 3.2 Click → reveals inline input, save/cancel buttons
- [ ] 3.3 Save reloads the modal content

## 4. Tests

- [ ] 4.1 Test edit text answer
- [ ] 4.2 Test edit number answer
- [ ] 4.3 Test edit choice answer
- [ ] 4.4 Test create answer for blank cell
- [ ] 4.5 Test viewer cannot edit (403)
