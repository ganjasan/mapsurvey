## Context

`write_ogr` converts every geo layer with one `ogr2ogr` call over an OGR VRT. Reproduced with a VRT
holding one bow-tie polygon and one square:

| Driver | Plain | `-makevalid` |
|---|---|---|
| GPKG | ok, invalid polygon kept | ok, MultiPolygon in a Polygon layer (spec warning) |
| ESRI Shapefile | ok, invalid polygon kept | ok |
| KML (no libkml) | ok | ok |
| LIBKML | exit 1 (prod 3.10, app test on 3.8); bare 3.8 run: placemark without geometry | ok, both features with geometry |

## Decisions

- **Repair in the KML writer only, not in `collect()`.** `collect()` feeds every format. Repairing
  there would change the GeoJSON and WKT that are the raw record of what the respondent drew, and
  would turn Polygon layers into mixed Polygon/MultiPolygon for GeoPackage (a conformance warning).
  The defect exists only where the driver rejects the geometry.
- **Apply to both KML drivers, not just LIBKML.** The flag is a no-op for valid input, and one code
  path keeps the plain KML fallback consistent with LIBKML.
- **No skip-and-report fallback.** `-makevalid` turns every polygon GEOS can read into a valid one,
  so there is nothing left to skip. A future driver error still surfaces as `ExportFailed`, as today.

## Risks

- A GDAL without GEOS refuses the flag and fails every KML export. Debian's and Ubuntu's `gdal-bin`
  link GEOS, and the test exercises the real binary wherever `OGR_AVAILABLE`.
