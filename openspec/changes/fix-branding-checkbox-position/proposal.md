## Why

In the Build "Survey settings" panel the "Show the Made with Mapsurvey badge" checkbox leaves
its row: it carries Bootstrap's `.form-check-input` (`position: absolute`) without the
`.form-check` parent that class expects, so it is placed against a container outside the
scrolling `.pr-scroll` and stays put while the panel scrolls. A creator sees an unlabelled
checkbox floating over the Survey period card and no switch next to the badge text.

## What Changes

- `editor_base.html`: `.pr-field label > .form-check-input` is `position: static; margin: 0`,
  so a checkbox written inside a `.pr-field` label sits in that label's flex row.
- Test in `survey/tests/test_viral_loop_branding.py` pins the markup shape and the rule.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None — a layout defect; the badge switch's behaviour is unchanged.

## Impact

`survey/templates/editor/editor_base.html` (CSS only). The standalone settings page keeps its
`.form-check` wrapper and is unaffected.
