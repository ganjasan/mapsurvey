# Proposal: fix-analytics-map-collapse

## Why

The Responses → Map tab renders an empty panel while its header counts features.
`switchAnalyticsTab()` sets `pane-data.style.display = ''`, erasing the inline
`display:flex` that the split-pane height chain hangs from; every descendant
collapses and `#analytics-map` gets 0px height. On mobile this runs at page load
(`mobileAnalyticsPane('charts')`), so the Map pane is always empty on phones; on
desktop it triggers after any Data ↔ Performance round-trip. Reproduced both ways.
PostHog Replay Vision surfaced it as a 7/10-frustration session (rage click on the
Map button); the same session hit `panel.requestFullscreen is not a function` —
iOS Safari has no unprefixed Fullscreen API, and the expand buttons call it bare.

## What Changes

- `switchAnalyticsTab` restores `display:'flex'` for `#pane-data` instead of `''`.
- Fullscreen toggles go through guarded helpers (unprefixed → webkit-prefixed →
  no-op), so browsers without the API get an inert button, not a TypeError.

## Capabilities

### New Capabilities

- `analytics-data-workspace`: layout invariants of the Responses Data workspace
  (split-pane height chain, panel fullscreen behavior). Narrow delta; a fuller
  spec of the workspace can grow here later.

### Modified Capabilities

_None._

## Impact

- `survey/templates/editor/analytics_dashboard.html` only (JS in template).
- No server, model, CSS-file, or respondent-facing changes.
