# Design: fix-analytics-map-collapse

## Context

Hotfix-scale change; full analysis in the proposal. `#pane-data` carries its
flex-column layout as an inline style; `switchAnalyticsTab` cleared it with
`style.display = ''`.

## Decisions

- **Restore `'flex'` in the switcher, not a CSS refactor.** Moving the layout
  into a stylesheet class is the cleaner long-term shape, but touches selector
  precedence for the `:fullscreen` rules and the mobile overrides — wrong risk
  profile for a hotfix. The one-word fix restores exactly the state the page
  loads with.
- **Guarded fullscreen helpers instead of hiding the buttons.** `_enterFullscreen`
  tries unprefixed then `webkitRequestFullscreen` (iPad works, iPhone becomes a
  no-op). Hiding the control per-capability is UI polish that can ride a later
  change; the hotfix only removes the TypeError.

## Risks / Trade-offs

- [`fullscreenchange` listener stays unprefixed] → on webkit-prefixed browsers
  the modal-relocation nicety doesn't run; no error, cosmetic only.

## Migration Plan

Single PR to master; revert to roll back.
