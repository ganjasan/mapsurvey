# Draw a reference overlay layer directly in the editor

**Type**: feature
**Priority**: medium
**Area**: frontend
**Created**: 2026-08-25

## Description

Instead of uploading a GeoJSON, the creator draws the reference layer (zones, a study
boundary, a route) right on the editor map and edits feature attributes (name, key) in
place. Split out of [reference overlay layers](feature-reference-overlay-layers.md)
(FD-1) during scoping (2026-08-25): FD-1 ships upload-only; drawing waits for the first
real request from a creator who has no digitized zones and no GIS.

## Scope sketch

- Leaflet.draw is already on every map surface — the drawing itself is cheap.
- The expensive part is the attribute editor: per-feature name/key/label editing UI,
  because a drawn layer without addressable features can't serve
  [answer-driven map context](feature-answer-driven-map-context.md) (FD-14).
- Output is a normal FD-1 layer (same storage, same config), so respondent rendering,
  serialization and delivery need zero changes — this is editor-side only.

## Notes

- Interim answer for the no-GIS creator: geojson.io (free, browser) or "send us your
  paper map" as a service touch — the service-model hypothesis applies.
- Epic: field-data-collection (FD-17)
