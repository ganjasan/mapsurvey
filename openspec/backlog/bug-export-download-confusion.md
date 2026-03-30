# Export vs Download confusion

**Type**: bug
**Priority**: high
**Area**: frontend
**Created**: 2026-03-26

## Description

Users confuse "Export survey" (backup/import format — survey.json + responses.json) with "Download data" (GIS export — .geojson + data.csv). Manuel Frost downloaded the survey backup, tried to open responses.json in QGIS as GeoJSON, and thought the export was broken.

"Export" and "Download" are synonyms for most users. Having two separate functions with similar names and no clear distinction is a UX trap.

## Proposed Solutions

- Rename "Export survey" → "Backup survey" or "Save survey template"
- Rename "Download data" → "Export data (GeoJSON/CSV)" — make it clear this is the GIS export
- Add format description next to each button: "For QGIS/ArcGIS use Export Data"
- Or: merge both into one download page with format options

## Notes

- Source: Manuel Frost (manu04) — reported as "GeoJSON doesn't open in QGIS" but the actual problem was downloading the wrong file
- This is probably why the "GeoJSON export bug" was reported — it may not be a bug at all, just UX confusion
