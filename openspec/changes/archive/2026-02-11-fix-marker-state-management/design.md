## Context

The survey map UI uses Leaflet + Leaflet.Draw for placing and editing geographic features (point markers, lines, polygons). State is managed through a handful of global variables:

- `currentQ` — the question code being answered
- `currentDrawFeature` — the active L.Draw handler or the layer being edited
- `editableLayers` — the L.FeatureGroup holding all drawn features

Draw buttons (`.drawpoint`, `.drawline`, `.drawpolygon`) create an L.Draw handler and call `.enable()`. The `draw:created` event in `survey_section.html` adds the layer to `editableLayers` and optionally opens a popup for sub-questions. Editing is triggered from popup buttons and reuses `currentDrawFeature` to hold the layer reference.

Three bugs stem from sloppy state transitions:
1. Draw handlers are never disabled after feature creation — users can spam-click markers.
2. Starting a second edit doesn't finish the first — both layers enter edit mode, only one is tracked.
3. All popups share `id="subquestion_form"` — jQuery's `$('#subquestion_form')` grabs the wrong DOM node when multiple popups have existed.

## Goals / Non-Goals

**Goals:**
- After a feature is placed on the map, the draw tool is deactivated immediately (single-shot draw)
- Only one feature can be in edit mode at a time
- Each popup's sub-question form is independently addressable so property serialization is correct

**Non-Goals:**
- Multi-feature placement mode (click once per feature is intentional)
- Changing the sub-question data model or GeoJSON output format
- Refactoring the drawbar / draw_button flow (kept as-is)
- Addressing line/polygon draw UX (they use the drawbar flow which already has stop/cancel)

## Decisions

### 1. Disable draw handler in `draw:created`, not in popup callbacks

**Decision:** Call `currentDrawFeature.disable(); currentDrawFeature = null;` at the top of the `draw:created` handler, before opening the popup.

**Rationale:** The draw handler's job ends the moment a feature is created. Tying deactivation to the popup lifecycle (Apply/Close) leaves a window where the user can click the map again. Disabling immediately is simpler and covers all geometry types.

**Alternative considered:** Disable in `endDrawMode()` only — rejected because `endDrawMode()` is not always called (e.g. when a popup with sub-questions opens).

### 2. Guard `startEditMode` against concurrent edits

**Decision:** At the start of `startEditMode(layer)`, check if another layer is already being edited (tracked in a new variable `currentEditLayer`). If so, call `currentEditLayer.editing.disable()` before proceeding.

**Rationale:** Using a dedicated `currentEditLayer` variable (separate from `currentDrawFeature`) avoids overloading `currentDrawFeature` for two different purposes (draw handlers vs layer editing). This makes the state machine clearer.

**Alternative considered:** Reuse `currentDrawFeature` for both — rejected because `L.Draw.Marker` and `L.Marker` have different APIs (`disable()` vs `editing.disable()`), mixing them is error-prone.

### 3. Unique form IDs per popup using Leaflet's layer ID

**Decision:** Replace the hardcoded `id="subquestion_form"` with `id="subquestion_form_<leaflet_id>"` where `<leaflet_id>` is `L.Util.stamp(layer)` (Leaflet's built-in unique layer ID). Update all `$('#subquestion_form')` references to use the layer-scoped ID.

**Rationale:** `L.Util.stamp()` is already available (it's how Leaflet tracks layers internally), requires no external counter, and is unique per layer for the lifetime of the page.

**Alternative considered:** Generate an incrementing counter — works but introduces unnecessary state when Leaflet already provides unique IDs.

### 4. Scope `onPopupOpen` / `onPopupClose` form queries to the popup DOM

**Decision:** In `onPopupOpen` and `onPopupClose`, query form elements relative to the popup's own DOM container (`this.getPopup().getElement()`) instead of using global `$('#subquestion_form')`. Store the form ID on `layer.feature.properties._formId` for the Apply handler.

**Rationale:** Even with unique form IDs, using a scoped query is more robust — it eliminates any possibility of cross-popup interference.

## Risks / Trade-offs

- **Risk: Existing answers restoration also uses `id="subquestion_form"`** → Mitigation: the same fix (unique IDs) applies to the restoration loop in `survey_section.html` lines 190-208.
- **Risk: `endEditMode` called without matching `startEditMode`** → Mitigation: `currentEditLayer` is null-checked before calling `.editing.disable()`.
- **Risk: Disabling draw handler in `draw:created` might interfere with line/polygon drawbar flow** → Mitigation: For lines/polygons, `draw:created` fires after the shape is complete, so disabling is correct. The drawbar "stop" button will also just be a no-op if the handler is already disabled.
