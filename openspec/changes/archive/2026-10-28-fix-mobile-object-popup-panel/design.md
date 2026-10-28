# Design: fix-mobile-object-popup-panel

`openObject()` calls `hidePanelForPopup(state)`: on `isMobile()` with the panel visible it
runs `toggleInfo(false)` (the shell's own function, which also flips `sidebar-hidden` for
the map controls) and remembers it did; the popup's `popupclose` for the current popup calls
`reshowPanel(state)` so the list returns for the next mark. Desktop is untouched: the panel
and the map do not overlap there.
