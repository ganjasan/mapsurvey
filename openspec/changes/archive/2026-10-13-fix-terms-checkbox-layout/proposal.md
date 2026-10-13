## Why

On `/accounts/register/` the "I am 16 or older and accept the Terms of use" checkbox (added in #290) renders alone, centred on a line above its text. It reads like a stray control, and people miss it. Issue #300.

## What Changes

- The terms row lays out as a normal checkbox row: the box at its natural size on the left, the label text beside it, wrapping under itself.
- Clicking the text still toggles the box, which it already does: the input sits inside its `<label>`.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `registration-abuse-defenses`: the age-and-terms requirement gains a layout scenario.

## Impact

- `survey/templates/base.html` (auth-card styles) and one class on the field's wrapper in `registration_form.html`. No behaviour or validation change.
