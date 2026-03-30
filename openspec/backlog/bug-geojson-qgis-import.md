# GeoJSON export not importable in QGIS

**Type**: bug
**Priority**: high
**Area**: backend
**Created**: 2026-03-26

## Description

User Manuel Frost (Berlin Senate) reports that exported GeoJSON cannot be imported into QGIS. QGIS says "it's not actually GeoJSON". Tried JSON Eater and QuickGeoJSON plugins — neither worked. Developer tested on his end and it opens fine — may be edge case with polygon data or encoding issue.

## Notes

- Source: Manuel Frost (manu04), survey "RuE" with polygon questions
- Waiting for him to send the exported archive for investigation
- Could be: invalid GeoJSON structure, BOM encoding, missing CRS, or coordinate precision issue
- Reported 2026-03-26
