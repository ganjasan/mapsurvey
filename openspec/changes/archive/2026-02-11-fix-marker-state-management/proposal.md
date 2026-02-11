## Why

Multiple users report bugs with map marker state: the draw tool stays active after placing a marker (allowing accidental spam-clicks), editing multiple points causes duplication, and sub-question data can be lost when multiple markers exist. These issues degrade survey data quality and confuse respondents.

## What Changes

- Deactivate the draw tool immediately after a marker/line/polygon is placed on desktop (call `endDrawMode()` or `currentDrawFeature.disable()` in the `draw:created` handler, before the popup opens)
- Enforce single-edit mode: when starting to edit a new marker, finish/disable any previously active edit first
- Fix duplicate `id="subquestion_form"` across all marker popups — each popup's form must have a unique ID so `serializeArray()` captures the correct form data
- Ensure `onPopupClose` saves properties using the popup's own form reference, not a global DOM query

## Capabilities

### New Capabilities
- `marker-draw-lifecycle`: Rules for activating, completing, and cancelling draw/edit mode for all geometry types (point, line, polygon) on both desktop and touch devices
- `marker-popup-isolation`: Rules for popup form identity and property serialization so that each marker's sub-question form is independent

### Modified Capabilities
- `mobile-point-crosshair`: Crosshair apply/cancel must respect the new draw lifecycle (no functional change expected — crosshair already calls `endDrawMode()` — but the spec should reference the lifecycle rules)

## Impact

- **Templates**: `base_survey_template.html` (draw button handlers, `startEditMode`, `endDrawMode`), `survey_section.html` (`draw:created` handler, popup binding, `onPopupOpen`/`onPopupClose`, feature restoration)
- **No backend changes**: all fixes are client-side JavaScript
- **No data model changes**: GeoJSON format and form submission remain the same
