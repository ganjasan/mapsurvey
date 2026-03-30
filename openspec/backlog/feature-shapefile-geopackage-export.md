# Shapefile and GeoPackage export

**Type**: feature
**Priority**: high
**Area**: backend
**Created**: 2026-03-26

## Description

Add Shapefile (.shp) and GeoPackage (.gpkg) export options alongside the current GeoJSON/CSV. Most GIS professionals work with these formats natively in QGIS, ArcGIS, etc.

## Notes

- Source: Manuel Frost (manu04) — "very important!"
- Python libraries: Fiona, geopandas, or osgeo/ogr for format conversion
- GeoPackage is a single-file SQLite format, good default for QGIS users
