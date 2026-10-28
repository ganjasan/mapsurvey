# Fix: "Dashboard" in the editor navbar loops back to the create page for new creators

## Why
`views.editor` redirects a creator whose organization has no surveys to
`/editor/surveys/new/?welcome=1`. The navbar's "← Dashboard" link points at bare
`/editor/`, so for exactly those creators the click reloads the create page.
Session replays (2026-09-09) show first-time creators clicking it repeatedly.

## What changes
- The navbar "Dashboard" link in `editor_base.html` carries `?dashboard=1`, the same
  escape flag the "Skip to dashboard" and "Cancel" links already use.
- Spec: the escape flag requirement now names the navbar link as well.

- Bundled: on the same page the Leaflet picker painted over the navbar dropdowns
  (language, workspace) because its wrapper formed no stacking context; `.create-map-wrap`
  gets `z-index: 0`, the same isolation `#map` already has on respondent pages.

## Out of scope
Whether the no-surveys redirect should exist at all.
