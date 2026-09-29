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

- **2026-09-29 — BUILT** in change `responses-export-formats` (branch
  `feature/responses-export-formats`, PR pending). `?format=gpkg|shp|kml` through one `ogr2ogr` call over an OGR VRT of the per-question GeoJSON (GDAL was already in the image). GeoPackage is recommended in the dialog; Shapefile ships as a ZIP with `ENCODING=UTF-8` and the 10-character field-name note.
