# analytics-data-workspace Specification (delta)

## ADDED Requirements

### Requirement: The heat layer does not draw into a zero-size canvas
The analytics heat layer SHALL skip its redraw while its canvas has no width or height.
`leaflet.heat` draws by reading the canvas back with `getImageData`, which throws `IndexSizeError`
on a `0×0` canvas, and Leaflet sizes that canvas from the map — so every `invalidateSize()` on a
hidden pane fires the failing redraw.

The guard SHALL live on the layer, not on the callers: `invalidateSize()` is called from sixteen
places across the analytics templates, and a per-caller guard would neither cover all of them
reliably nor cover the next one added.

#### Scenario: Resizing a hidden pane draws nothing
- **WHEN** the map's pane is hidden and a resize is triggered by a pane switch, a drag, a modal, or a layout change
- **THEN** the heat layer skips its redraw and no error is raised

#### Scenario: A visible heat layer still draws
- **WHEN** the map pane is visible and the heat layer is redrawn
- **THEN** it draws as before
