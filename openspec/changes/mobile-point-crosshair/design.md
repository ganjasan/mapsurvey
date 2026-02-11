## Context

Point placement currently uses Leaflet.Draw's `L.Draw.Marker` — the user clicks/taps the map and a marker appears at the tap location. On touchscreen devices this is problematic:

1. The info panel covers the entire screen, so users must first close it to see the map — but nothing tells them to do this.
2. Tapping the map with a finger is imprecise — fat-finger problem makes it hard to place a marker accurately.
3. After tapping, if the question has sub-questions, a popup opens — on small screens this can obscure the map entirely.

The existing code handles point clicks in `base_survey_template.html` (line 436, `.drawpoint` click handler) which creates `L.Draw.Marker` and calls `.enable()`. The info panel is hidden via `toggleInfo(false)`.

## Goals / Non-Goals

**Goals:**
- Replace tap-to-place with a crosshair-based flow on touchscreen devices (`pointer: coarse`)
- Show a fixed crosshair in the center of the map with Cancel/Apply buttons
- User pans the map to aim, then confirms — intuitive and precise
- Integrate seamlessly with existing sub-question popups and geo answer serialization

**Non-Goals:**
- Changing line or polygon drawing behavior
- Changing the desktop (mouse/trackpad) point placement flow
- Redesigning the info panel or mobile layout beyond hiding it during crosshair mode
- Adding GPS/geolocation-based placement

## Decisions

### 1. Touch detection: `pointer: coarse` media query

**Choice**: `window.matchMedia('(pointer: coarse)').matches`

**Alternatives considered**:
- `'ontouchstart' in window` — detects touch capability but fires true on laptops with touchscreens where the user primarily uses a mouse
- `navigator.maxTouchPoints > 0` — same problem as above
- Viewport width `≤768px` — doesn't account for tablets with large screens or desktop touch monitors

`pointer: coarse` detects that the _primary_ pointing device is imprecise (a finger), which is exactly the condition where crosshair mode helps.

### 2. Crosshair as a fixed-position HTML overlay (not a Leaflet layer)

**Choice**: A `<div>` with `position: fixed` centered on the screen, containing a crosshair icon (FontAwesome `fa-crosshairs` or `fa-plus`) and two buttons below.

**Alternatives considered**:
- Leaflet marker pinned to map center via `map.on('move')` — adds complexity, the marker would need constant repositioning and would interact with Leaflet's internal layer management
- CSS `::after` pseudo-element on `#map` — can't contain interactive buttons

The overlay approach is simpler: it doesn't interact with Leaflet at all. On Apply, we just read `map.getCenter()` to get the coordinates.

### 3. Crosshair overlay structure

```
#crosshair-overlay (fixed, centered, z-index: 15, pointer-events: none)
├── .crosshair-icon (the crosshair marker icon — uses the question's icon and color)
└── .crosshair-actions (pointer-events: auto)
    ├── button.crosshair-cancel (red, ✕ icon)
    └── button.crosshair-apply (green, ✓ icon)
```

- The overlay itself has `pointer-events: none` so the map remains pannable underneath
- Only the action buttons have `pointer-events: auto`
- The crosshair icon is positioned at the visual center of the map
- Buttons are positioned below the crosshair with enough spacing to not interfere with panning

### 4. Integration with existing draw flow

**On `.drawpoint` click (touch device)**:
1. Do NOT create `L.Draw.Marker` — skip Leaflet.Draw entirely
2. Hide info panel (`toggleInfo(false)`)
3. Show `#crosshair-overlay` with the question's icon/color
4. Store `currentQ` (question code) as usual

**On Apply button click**:
1. Read `map.getCenter()` → `[lat, lng]`
2. Create an `L.marker` at that position with the question's icon/color
3. Set up `feature.properties.question_id = currentQ`
4. Bind the sub-question popup (same as current `draw:created` handler)
5. Add to `editableLayers`
6. Hide crosshair overlay
7. If sub-questions exist, open popup; otherwise call `endDrawMode()`

**On Cancel button click**:
1. Hide crosshair overlay
2. Show info panel (`toggleInfo(true)`)
3. Reset `currentQ`

This approach reuses the existing marker creation, popup binding, and serialization code. The only difference is _how_ the lat/lng is determined (map center vs. tap location).

### 5. Crosshair icon reflects the question's marker style

The crosshair should show the same FontAwesome icon and color as the final marker (from `data-icon` and `data-color` attributes on the `.drawpoint` button). This gives the user a preview of what will be placed. The icon is rendered at a larger size (e.g., 40px) for visibility.

### 6. File organization — all changes in existing files

- **`base_survey_template.html`**: Add crosshair overlay HTML + JS logic for entering/exiting crosshair mode
- **`main.css`**: Add crosshair overlay styles
- No new files needed. The crosshair JS is small enough to live inline alongside the existing draw logic.

## Risks / Trade-offs

**[Risk] `pointer: coarse` misclassifies some devices** → On hybrid devices (e.g., Surface with keyboard detached), the primary pointer may switch. This is an acceptable edge case — the crosshair UX works fine with a mouse too, it's just not necessary. No mitigation needed.

**[Risk] Map center may not be where the user expects** → The crosshair icon visually anchors the center. As long as the icon is accurately centered (using `position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%)`), this is reliable.

**[Risk] Buttons too close to crosshair could interfere with panning** → Place buttons ~60px below the center with adequate touch target size (min 44x44px per WCAG). The overlay div itself has `pointer-events: none`.
