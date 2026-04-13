## Context

Survey respondent maps use Leaflet.draw 1.0.4 for polygon and line input. Drawing is triggered programmatically via `new L.Draw.Polygon(map).enable()` / `new L.Draw.Polyline(map).enable()` from `.drawpolygon`/`.drawline` button click handlers. The native Leaflet.draw toolbar is hidden (all draw types set to `false`). Point placement uses a separate crosshair overlay with visible Cancel/Apply buttons fixed at the bottom of the screen.

The existing `#drawbar` div has a single `#draw_button` with a state machine (`start_draw`/`stop_draw`/`end_edit`), but polygon/line handlers bypass it entirely — `startDrawMode()` is dead code (only called from commented-out lines).

## Goals / Non-Goals

**Goals:**
- Add visible "Cancel" and "Finish drawing" buttons during polygon/line drawing
- Disable "Finish drawing" until minimum vertex count (polygon: 3, line: 2)
- Move edit-mode finish button to the same bottom-fixed position
- Match the visual pattern of the crosshair overlay action bar
- Support i18n for all new button labels

**Non-Goals:**
- Changing the crosshair overlay for point placement (already works well)
- Adding undo-last-vertex button (separate improvement)
- Applying to editor analytics map or map picker (respondent forms only)

## Decisions

### 1. Repurpose `#drawbar` as bottom-fixed action bar

**Decision**: Replace the existing `#drawbar` (single top-positioned button) with a bottom-fixed bar containing Cancel + Finish buttons, matching `#crosshair-overlay .crosshair-actions` positioning.

**Rationale**: Reuses existing DOM element and show/hide logic (`toggleDrawbar`). Consistent with the crosshair UX pattern that respondents already see for point placement.

### 2. Track vertex count via `draw:drawvertex` event

**Decision**: Listen to `map.on('draw:drawvertex')` to count placed vertices and enable/disable the Finish button.

**Rationale**: Leaflet.draw fires `draw:drawvertex` each time a vertex is added. We read `currentDrawFeature._markers.length` from the handler to check against the minimum. This avoids patching Leaflet.draw internals.

### 3. Use `completeShape()` API for programmatic finish

**Decision**: Finish button calls `currentDrawFeature.completeShape()`.

**Rationale**: This is the public API method used by Leaflet.draw's own toolbar "Finish" action. It validates the shape and fires `draw:created`. It's a no-op if the shape is invalid, providing a safe fallback.

### 4. Reuse bar for edit mode with label swap

**Decision**: Edit mode shows the same bottom bar with "Cancel" hidden and "Finish editing" label on the finish button.

**Rationale**: Single UI pattern for all map action bars. Less code, more consistency.

### 5. Remove dead code

**Decision**: Remove `startDrawMode()` function and old `#draw_button` click handler state machine.

**Rationale**: `startDrawMode()` is only referenced from commented-out lines. The `#draw_button` handler is replaced by the new Cancel/Finish buttons.

## Risks / Trade-offs

- **[Risk] `_markers` is internal Leaflet.draw API** → Mitigated: it's stable in 1.0.4, and `completeShape()` itself uses it. No alternative public API for vertex count.
- **[Risk] `draw:drawvertex` doesn't fire on vertex removal** → Acceptable: Leaflet.draw 1.0.4 polyline/polygon don't support vertex removal during initial draw, only during edit mode.
- **[Trade-off] Edit mode Cancel hidden** → Simpler than adding undo-edit logic; user can click away to close the edit.
