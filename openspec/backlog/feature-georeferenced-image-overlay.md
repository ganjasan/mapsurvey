# Georeferenced image overlay — a plan drawing on top of the real map

**Type**: feature
**Priority**: medium
**Area**: frontend
**Created**: 2026-08-25

## Description

A creator uploads a raster image (architect's park-renewal plan, a scanned zoning sheet,
a rendered masterplan) and places it on the geographic map as a semi-transparent
`L.imageOverlay`; respondents leave their comments and geometry on top of it. The case
that surfaced it: "Оставьте свои предложения на этом плане обновления парка" — in real
Bürgerbeteiligung the plan is almost always a PDF/render, not a GeoJSON.

Split out of [reference overlay layers](feature-reference-overlay-layers.md) (FD-1)
during scoping (2026-08-25): FD-1 ships vector-only, but its layer model is designed
extensible (`type: vector | image`) so this feature adds a type, not a migration.

## Scope sketch

- Upload an image (PNG/JPEG; PDF conversion out of scope) + opacity slider.
- Georeferencing UX is the actual project: manual corner coordinates are unusable for
  the non-GIS creator, so this needs interactive placement — drag/scale/rotate the image
  on the editor map (Leaflet.DistortableImage-class interaction) — or at minimum a
  two-point alignment flow.
- Bounds + opacity stored in the layer config; image file follows the same storage,
  delivery and ZIP round-trip paths FD-1 establishes.

## Notes

- NOT the same as [custom image basemap](feature-custom-image-basemap.md): that one
  leaves geography entirely (`CRS.Simple`, non-geo coordinates); this one overlays an
  image on the normal WGS84 map and all answers stay ordinary geography.
- Epic: community-engagement (the buyer is a planning/participation project;
  Ideenkarte-class parity).
