## Context

Seven placement paths in `base_survey_template.html` call `toggleInfo(false)`: `startEditMode`,
`startPaintMode`, the pop-up's "move point" (`layer-edit` on a marker, which also `panTo`s the
marker to the map centre), `.drawpolygon`, `.drawline`, `.drawpoint` and tap-to-place. The
crosshair overlay is `position: fixed` over the whole viewport and flex-centres the pin;
`getCrosshairLatLng()` reads the point under `size/2 + 32 px`; its Cancel/Apply and `#drawbar`
are `left: 50%`. `_subquestionPopupOptions()` pads auto-pan by the panel's right edge — written
when the panel could only be on the left. `#map` fills the viewport, so viewport x == map
container x.

## Goals / Non-Goals

**Goals:** an opt-in per-section setting; with it, no panel hiding on desktop map sections and
every placement aid centred on the visible map; without it, today's behaviour byte for byte;
the pop-up padding fixed for a right-hand panel.

**Non-Goals:** offsetting the section's start view (`moveMapTo` on section entry) or
geolocation by the panel; any change on phones; a survey-level default.

## Decisions

### D1. `keep_panel_open` BooleanField on the section
Per section, like every other layout control, so a creator can keep the panel on a long
"mark several places" page and not on a quick one. A boolean, not a choice: there is no third
state. `layout_classes()` adds `panel-keep` for `map` sections only; `#section-data` carries
`data-keep-panel-open`; `initSection()` toggles the class.

### D2. One decision helper, one geometry helper
- `keepPanelWhilePlacing()` = `body.panel-keep && !isMobile()`.
- `hidePanelForPlacement()` replaces the seven `toggleInfo(false)` calls: it calls
  `toggleInfo(false)` unless `keepPanelWhilePlacing()`. The `toggleInfo(true)` calls on finish
  and cancel stay — showing a shown panel is a no-op.
- `visibleMapArea()` returns `{left, width}` in viewport px: the full viewport unless the
  panel is kept AND open, else the viewport minus the panel's bounding box on its side (read
  from `getBoundingClientRect()`, so side, width presets and the content settings never need
  their own branches).

### D3. Placement aids follow the area
- `showCrosshair()` sets the overlay's `left`/`width` to the area and the actions' `left` to its
  centre; `hideCrosshair()` clears the inline styles.
- `getCrosshairLatLng()` uses `area.left + area.width / 2` instead of `size.x / 2`.
- `showDrawbar()` sets `#drawbar`'s `left` to the area's centre; `hideDrawbar()` clears it.
- The marker "move" path computes the pan target so the marker lands at the area's centre
  (`markerPoint + (mapCentre − areaCentre)`), still one `panTo`.
With the setting off the area is the viewport, so the arithmetic yields today's values; the
inline styles are only written when the area differs from the viewport, so default rendering
is untouched.

### D4. Pop-up padding by side (bug fix, independent of the setting)
`_subquestionPopupOptions()` pads `TopLeft.x` by the panel's right edge when the panel is on
the left (today) and `BottomRight.x` by `innerWidth − panel.left` when it is on the right.

### D5. Editor, travel, API — as #473/#476
Checkbox after `content_valign`, visible only for the Map stage (`syncLayoutControls`); a POST
without the field must keep the stored value, so the form reads it as a tri-state from
`data` (absent = keep), not as a plain BooleanField (an absent checkbox means False).
`plain_field_values` carries it; ZIP export + `bool` import (non-bool → False); `SectionIn`
`Optional[bool]`, `SectionOut`, `forms_bridge.SECTION_FIELDS`, MCP description; references
regenerated. Safe edit (not in `structural_section_changes`). The epic's card gets a sentence.

## Risks / Trade-offs

- Line/area drawing with Leaflet.draw: vertices are clicked on the map, which is unaffected by
  the panel; the first-vertex tooltip follows the cursor. Nothing to offset.
- Spray paint listens on the map container; the panel is a sibling above it, so painting under
  the panel is impossible by construction — the respondent paints in the visible area.
- The checkbox-absent rule (D5) is the one place this differs from the choice fields; a test
  pins it.

## Migration Plan

Migration `0108`: one boolean with default False. Revert = drop it.
