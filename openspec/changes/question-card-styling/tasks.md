## 1. Form infrastructure

- [x] 1.1 In `SurveySectionAnswerForm.__init__`, set `self.fields[field_name].widget.input_type = question.input_type` after creating each field
- [x] 1.2 Create a custom template filter `is_card_question` in `survey/templatetags/` that returns True for input_types `text`, `text_line`, `number`, `choice`, `multichoice`, `range`

## 2. Template changes

- [x] 2.1 Replace `{{ form.as_p }}` in `survey_section.html` with field-by-field iteration: loop over `form`, render label + errors + widget per field, wrap card-eligible fields in `div.question-card`
- [x] 2.2 Render hidden fields separately via `{% for hidden in form.hidden_fields %}{{ hidden }}{% endfor %}`

## 3. CSS — question cards

- [x] 3.1 Add `.question-card` styles in `main.css`: white background, 12px padding, 8px border-radius, 1px solid #e0e0e0 border, 12px margin-bottom

## 4. CSS — custom radio buttons

- [x] 4.1 Hide native radio inputs (`opacity: 0; position: absolute`) inside `.question-card`
- [x] 4.2 Style radio labels with `::before` pseudo-element: 20px circle, 2px #333 border, and `:checked + label` fill with #1a73e8 and scale transition
- [x] 4.3 Ensure radio labels have min-height 44px with flex alignment for touch targets

## 5. CSS — custom checkboxes

- [x] 5.1 Hide native checkbox inputs (`opacity: 0; position: absolute`) inside `.question-card`
- [x] 5.2 Style checkbox labels with `::before` square indicator and `::after` checkmark on `:checked`, fill with #1a73e8 and transition
- [x] 5.3 Ensure checkbox labels have min-height 44px with flex alignment for touch targets

## 6. CSS — geo button consistency

- [x] 6.1 Update `.drawbutton` to have `border-radius: 8px` and `margin-bottom: 12px`

## 7. Testing

- [x] 7.1 Write test: text question renders inside `div.question-card`
- [x] 7.2 Write test: geo question (point) does NOT render inside `div.question-card`
- [x] 7.3 Write test: widget has `input_type` attribute set correctly
- [x] 7.4 Manual test: verify card appearance, radio/checkbox styling, and touch targets on mobile viewport
