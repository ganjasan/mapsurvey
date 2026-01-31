## Why

HTML5 form validation does not work with hidden required fields. When a geo-question (point/line/polygon) is marked as required, the hidden `<input>` element receives the `required` attribute. The browser cannot focus on hidden elements to display validation errors, resulting in:

```
An invalid form control with name='Q_xxx' is not focusable.
```

This blocks form submission entirely, preventing users from proceeding to the next survey section.

## What Changes

- Remove native HTML5 `required` attribute from hidden geo-input fields
- Add `data-required="true"` attribute to mark fields that need validation
- Implement JavaScript validation before form submission
- Show user-friendly error message when required geo fields are empty
- Prevent form submission until required geo points are placed on map

## Capabilities

### New Capabilities

- `geo-field-validation`: Client-side JavaScript validation for required geographic input fields (point, line, polygon) that cannot use native HTML5 validation due to hidden input implementation.

### Modified Capabilities

None - this is a bug fix that doesn't change existing spec-level requirements.

## Impact

- `survey/templates/leaflet_draw_button.html` - Remove `required`, add `data-required`
- `survey/templates/base_survey_template.html` - Add JS validation logic before form submit
- User experience: Users will see a clear error message instead of a cryptic browser error
