# Map image export (PNG) from Responses

**Type**: feature
**Priority**: low
**Area**: frontend
**Epic**: survey-analytics
**Created**: 2026-08-31

## Description

A consultant's deliverable is a report with a map figure in it. Today they screenshot the
Responses map. Maptionnaire lists "Map image export (.png)" in every tier; it is a
one-button expectation.

## Scope Sketch

- "Export image" on the Responses map: current extent, current filter/selection, heatmap
  or markers as shown, legend, attribution line — rendered client-side (`leaflet-image` or
  `dom-to-image`) at 2× for print.
- Same on the public results page map blocks for the creator only.

## Notes

Tile providers' terms: OSM tiles are fine with attribution; check the satellite provider.
