## Context

Three creator-facing pickers set a start position by click-to-place-marker:
`survey_settings.html` (standalone page, `.settings-main` capped at 800px by
`editor_base.html`), `partials/survey_settings_panel.html` (the same form swapped into the
editor by HTMX) and `partials/section_map_picker.html` (a Bootstrap modal, 400px map).
The first two carry duplicate inline scripts. `MapPlaceSearch.attach(map, {accessToken,
container|position, labels, onSelect})` renders into a given container or as a Leaflet
control, moves the map on select and calls `onSelect(result)`; it returns `null` without
a Mapbox token. The create page already styles the control above the map
(`.create-map-search`).

## Goals / Non-Goals

**Goals:**
- Search-then-save on every editor picker, on desktop and mobile.
- Enough map to frame a city on desktop without scrolling the page.

**Non-Goals:**
- Merging the two duplicated settings scripts (a refactor with no user-visible change;
  it can follow in its own change).
- Changing the click-to-set interaction model or the save endpoints.
- Section-level "inherit" semantics — unchanged.

## Decisions

**D1. Selecting a search result sets the position, not only the view.**
`onSelect(result)` places or moves the marker at the result point and updates the
lat/lng/zoom variables and the coords label, exactly as a click would. Rationale: the
control's default ("move the map, do nothing else") is right for respondents, whose point
must be a deliberate act; a creator searching for a city wants that city as the answer.
A subsequent click still refines. Alternative: keep view-only and rely on a click —
rejected as the same two-step dance we are removing.

**D2. Search sits above the map in a container, not as a Leaflet control.**
Mirrors the create page (`.create-map-search`), keeps the dropdown out of the map's
overflow/z-index and stays reachable on a phone keyboard. The section modal is the one
place a top-left Leaflet control would be tempting; the container is used there too for
consistency and because Bootstrap modal focus handling and Leaflet control click capture
interact badly.

**D3. Sizing.**
Settings page: the "Default Map Position" section gets `max-width: none` on ≥1024px and
the map 460px tall; the rest of `.settings-main` stays 800px. In-editor panel: 380px on
≥1024px. Section modal: `modal-lg` with a 480px map on ≥1024px. Below 1024px all three keep
today's heights (300/300/400) so the mobile nav overlays still fit; the mobile win is the
search box.

**D4. Script loading.**
`map_place_search.js` is added to `editor_base.html` (covers panel and modal, both swapped
into the editor page) and to `survey_settings.html`. The include in `survey_create.html`
stays. The control is inert without a Mapbox token, so unconfigured environments render
the pickers as before.

**D5. Section modal and the inherit checkbox.**
While "Inherit position" is checked the picker has `pointer-events: none`; a search there
would move a map the creator cannot then click. On select, the modal unchecks inherit and
runs the existing `updatePickerState()` before applying D1, so the search result becomes
the section's own position — which is what typing a place into a section picker means.

## Risks / Trade-offs

- [Mapbox request cost from three more surfaces] → same debounce/min-chars throttle as
  the create page; creator-only traffic; Photon fallback is free.
- [Two copies of the settings script drift] → both are edited in this change with the
  same block; a follow-up refactor is noted in Non-Goals.
- [Wider settings section looks detached from the 800px column] → only that section
  widens and it keeps the same card styling; check visually during implementation.

## Migration Plan

Template/CSS only; normal merge, revert to roll back.

## Open Questions

None.
