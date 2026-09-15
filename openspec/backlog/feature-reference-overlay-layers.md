# Reference overlay layers on the respondent map

**Type**: feature
**Priority**: high
**Area**: frontend
**Created**: 2026-08-23

## Description

A creator uploads a GeoJSON (or draws it) that renders as a non-interactive layer under the
respondent's map: counting zones, district boundaries, a study area, a planned route. The
respondent sees where they are supposed to work; they cannot edit or answer with it.

Third independent request: Olney needs each volunteer's counting zone shown
([[lead-olney-squirrel-count]] — the one requirement we had to decline in writing);
Ideenkarte already has it ([[competitor-ideenkarte]]); ThINK Jena will ask. Survey123's
having it is the main honest reason a municipality would pick ESRI over us.

## Notes

- Minimum viable: one uploaded GeoJSON per survey or per section, styled with one colour +
  optional label field, toggleable by the respondent.
- Next step up: per-volunteer zone highlighting, which needs volunteer links (FD-2).
- Watch the payload: 35 zones of hand-drawn street polygons is small, but a creator will
  eventually upload a 40 MB parcel layer — cap size and simplify server-side.
- Epic: field-data-collection (FD-1)
