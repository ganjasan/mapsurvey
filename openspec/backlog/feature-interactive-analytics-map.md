# Interactive Analytics Map

**Type**: feature
**Priority**: medium
**Area**: frontend
**Created**: 2026-04-02

## Description

Enhance the analytics Response Map into a full interactive exploration tool. Includes: geo layer toggles to show/hide layers per question, spatial cross-filtering (draw a rectangle or polygon on the map to filter all other charts by that geographic area), feature inspection (click a point or geometry to view all answers from that session), and fullscreen/detach mode to open the map in a separate window or expand to full viewport.

## Notes

- Builds on top of the cross-filtering infrastructure (answer matrix, FilterManager)
- Geo layers are already color-coded by question; layer toggles are a natural extension
- Spatial filtering would add a geographic dimension to the existing choice-based cross-filtering
- Feature inspection requires a new endpoint or client-side session lookup
