## 1. Template Changes

- [x] 1.1 Replace `required` with `data-required` in leaflet_draw_button.html
- [x] 1.2 Verify the template change renders correctly

## 2. JavaScript Validation

- [x] 2.1 Add validation function to check data-required geo fields
- [x] 2.2 Integrate validation into form submit handler in base_survey_template.html
- [x] 2.3 Prevent form submission when validation fails (e.preventDefault)

## 3. User Feedback

- [x] 3.1 Add visual highlighting (red border) to invalid draw buttons
- [x] 3.2 Display error message/alert when validation fails
- [x] 3.3 Scroll to first invalid field

## 4. Testing

- [ ] 4.1 Test form submission with required geo field empty (should block)
- [ ] 4.2 Test form submission with required geo field filled (should proceed)
- [ ] 4.3 Test form with multiple required geo fields
- [ ] 4.4 Test form with mix of required and optional geo fields

> **Manual testing required** - verify in browser

## 5. Additional Fixes

- [x] 5.1 Make `option_group` field optional in Question model
  - Added `blank=True` to allow saving questions without option_group in admin
  - Migration: `0002_option_group_blank.py`
