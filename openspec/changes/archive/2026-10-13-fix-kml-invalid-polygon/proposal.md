## Why

A respondent can draw a self-intersecting polygon (a "bow tie"). The answer is stored as drawn, and
every export format except KML writes it unchanged. KML is written through the LIBKML driver, which
refuses invalid polygons:

- on production (Debian 13, GDAL 3.10) `ogr2ogr` exits 1 (`ERROR 6: Invalid polygon … Cannot
  translate feature`), `ExportFailed` is raised and the creator gets **no file at all**: one
  respondent's shape blocks the whole survey's KML (issue #277; PostHog issue
  `01a1294b-244e-7361-8dff-d9b986955214`, 2026-10-11);
- the same failure reproduces through the app on GDAL 3.8 (local development). A bare `ogr2ogr`
  run on GDAL 3.8 can instead exit 0 and write that placemark **without geometry**, silently losing
  the respondent's shape. Either way the KML is wrong.

## What Changes

- The KML export passes `-makevalid` to `ogr2ogr`. GDAL repairs only invalid geometries (a bow tie
  becomes a two-part MultiPolygon covering the same area); valid ones pass through untouched.
- GeoJSON, CSV, Excel, GeoPackage and Shapefile are unchanged. They keep the geometry exactly as the
  respondent drew it, which is the raw data a GIS user may want to inspect.

## Impact

- Code: `survey/export.py::write_ogr` (KML branch only).
- Spec: `responses-export-formats`, the KML requirement gains a scenario.
- Runtime: `-makevalid` needs GDAL ≥ 3.1 built against GEOS ≥ 3.8. Debian's `gdal-bin` (the Docker
  image) and Ubuntu's both qualify.
