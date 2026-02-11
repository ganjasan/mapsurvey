## Context

The survey platform currently has two distinct UX paths for placing point markers on the map:

1. **Desktop** (`pointer: fine`): `L.Draw.Marker` — user clicks directly on the map to place a marker. The draw handler cursor follows the mouse.
2. **Touch/mobile** (`pointer: coarse`): Crosshair overlay — a fixed pin icon in the center of the screen; user pans the map, then taps Apply/Cancel.

The crosshair approach is more precise and intuitive on all devices because it decouples the "aim" action (panning) from the "confirm" action (button press). For editing existing markers, the current flow uses Leaflet's built-in `layer.editing.enable()` which allows dragging — this is fine for lines/polygons but clunky for single-point markers.

Key files:
- `survey/templates/base_survey_template.html` — crosshair overlay HTML, `showCrosshair()`/`hideCrosshair()`, `.drawpoint` click handler, `#draw_button` handler, `startEditMode()`/`endEditMode()`
- `survey/templates/survey_section.html` — `draw:created` handler, `onPopupOpen` (Edit/Delete/Apply button handlers), geo answer restoration
- `survey/static/css/main.css` — crosshair overlay styles

## Goals / Non-Goals

**Goals:**
- Use crosshair overlay for point placement on all devices (remove `isTouchDevice` gate)
- Use crosshair overlay for repositioning existing point markers (Edit button in popup)
- Remove `L.Draw.Marker` usage for point questions entirely
- Keep the UX for line and polygon drawing unchanged

**Non-Goals:**
- Extending crosshair mode to line/polygon editing
- Changing the crosshair visual design or animation
- Modifying backend data handling
- Changing info panel slide behavior (already works correctly)

## Decisions

### 1. Crosshair for all devices, not just touch

**Decision**: Remove the `isTouchDevice` conditional in `.drawpoint` click handler. Always call `showCrosshair(color, icon)`.

**Rationale**: The crosshair UX is superior to `L.Draw.Marker` even on desktop — it gives a clear visual cue and avoids the "ghost marker following cursor" pattern. Maintaining two code paths adds complexity.

**Alternative considered**: Keep both paths and add crosshair-edit only for touch. Rejected because it doubles testing surface and desktop users benefit from crosshair too.

### 2. Crosshair-based marker repositioning via Edit button

**Decision**: When the user clicks "Edit" on a point marker popup, the system will:
1. Store a reference to the layer being edited and its original LatLng
2. Close the popup
3. Pan the map to center on the marker's current position
4. Show the crosshair overlay (with the marker's color/icon)
5. On Apply: update the marker's LatLng to `map.getCenter()` and update the hidden geo input
6. On Cancel: restore original position (no-op since marker wasn't moved yet)

**Rationale**: This reuses the existing crosshair infrastructure. The user sees the same familiar UI for both placement and repositioning.

**Alternative considered**: Custom drag-to-reposition with a separate "confirm" step. Rejected — more complex to implement and inconsistent with the placement UX.

### 3. State management: crosshair edit mode vs. new placement mode

**Decision**: Add a `crosshairEditLayer` variable (null when not in edit mode). The crosshair Apply/Cancel handlers check this variable:
- If `crosshairEditLayer` is set → **edit mode**: move the existing marker, don't fire `draw:created`
- If `crosshairEditLayer` is null → **new placement mode**: fire `draw:created` as before

**Rationale**: Minimal state — one variable distinguishes the two modes. The crosshair UI is identical in both cases; only the Apply action differs.

### 4. Detect point vs. line/polygon for Edit button behavior

**Decision**: In `onPopupOpen`, check if the layer is an instance of `L.Marker`. If yes, the Edit button enters crosshair-repositioning mode. If no (line/polygon), keep the existing `startEditMode(layer)` behavior with Leaflet's drag handles.

**Rationale**: `L.Marker` instanceof check is the simplest and most reliable way to distinguish point features.

### 5. Hide the original marker during crosshair edit

**Decision**: While the crosshair overlay is showing for an edit, set `layer.setOpacity(0)` (or remove from map temporarily). On Apply, update position and restore. On Cancel, just restore visibility.

**Rationale**: Showing both the original marker and the crosshair pin would be visually confusing. Hiding the marker clarifies that it's being moved.

## Risks / Trade-offs

- **Desktop users accustomed to click-to-place**: Users who were used to `L.Draw.Marker` now get a different flow → Mitigation: The crosshair flow is simpler (pan + click Apply), and no existing surveys depend on the specific UX path.
- **Map pan on Apply centering**: When entering edit mode, `map.panTo(marker.getLatLng())` may cause a visible map movement → Mitigation: This is expected and helps orient the user. If the marker is already visible, the pan will be minimal.
- **`L.Marker` opacity**: Some Leaflet icon implementations (FontAwesome markers) may not fully support `setOpacity()` → Mitigation: Test with the actual `L.Icon.FontAwesome` used in the project. Fallback: temporarily remove the layer from `editableLayers` and re-add on Apply/Cancel.
