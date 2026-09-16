## Context

`section_map_picker.html` is rendered into `#mapPickerModalBody` by HTMX and runs one
`setTimeout(…, 300)` callback that creates the Leaflet map, includes `basemap_layers.html`,
defines `updatePickerState`, attaches the shared `MapPlaceSearch` control, then binds the Save
button, the My-location control and calls `invalidateSize`. Everything after a throw in that
callback is skipped, and the modal gives no sign of it: the map is already on screen.

Two edits produced the current state. PR #174 added the search block and closed its `onSelect`
callback two blocks too late, swallowing the click/zoom/inherit bindings. PR #180 renamed the
token global in the basemap partial and swept every reference it could find; the picker's
`accessToken: mapboxAccessToken` was missed because that name was also the respondent page's
legitimate global.

## Goals / Non-Goals

**Goals:** a section picker that saves what the creator clicks, with or without the search
control; a test that fails on either regression.

**Non-Goals:** changing the picker's interaction model (click-to-place vs centre-of-map, as the
create page does — that is a separate backlog card); the respondent-side "full page load of a
non-head section uses the survey-level position" quirk in `views.py`; the sub-question
visibility gap.

## Decisions

**Token as a template literal, not `_mapboxToken`.** Reading the partial's new private global
would recreate the coupling that broke. The settings page, the settings panel, the create page
and the analytics map all inline `'{{ MAPBOX_ACCESS_TOKEN }}'`; the section picker now does too.

**Search control attached last, after Save and `invalidateSize`.** The order inside the
callback is now: map, basemap, state helpers, inherit/click/zoom handlers, Save, My-location,
`invalidateSize`, search. Anything essential is bound before the one call that talks to an
external SDK. No `try/catch` around the attach: a throw there still reaches PostHog error
tracking, which is how this one was found, and the picker keeps working regardless.

**Structural tests over a JS runtime.** The Django test client renders the script; asserting
order of bindings and the absence of the bare identifier is enough to catch both regressions.
Executing the script under a stubbed Leaflet is more than a hotfix should carry.

## Risks / Trade-offs

- [Structural tests are brittle to harmless reformatting] → they assert three anchors only:
  `map.on('click'` before `MapPlaceSearch.attach(`, `save-map-position` binding before it, and
  no `clearCb.addEventListener` after `onSelect: function`.
- [A future partial rename could still break a template we did not test] → the lesson is in
  memory; the fix here removes the last cross-partial global read in the editor pickers.

## Migration Plan

Deploy. Nothing to backfill: the picker never wrote anything during the outage. Reply to the
BC3 creator once it is live. Rollback: revert the template.
