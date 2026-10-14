## 1. One card partial

- [x] 1.1 Move the section's field loop to `partials/question_fields.html`; include it from `survey_section_partial.html` and `question_preview_frame.html`
- [x] 1.2 Render `subquestions_forms` with that partial instead of `as_p()`

## 2. Popup behaviour and style

- [x] 2.1 `initPopupFields(root)` (ranking + rating chip) after restore in the feature popup and the object popup
- [x] 2.2 Frameless cards and the section base font size inside `.leaflet-popup-content`

## 3. Verification

- [x] 3.1 Test: popup form carries the hint in its card and the stars partial (fails on `as_p()`)
- [x] 3.2 Browser pass over every top-level type and every sub-question type in both popups, answers restored and saved
- [x] 3.3 Full `survey` suite once
