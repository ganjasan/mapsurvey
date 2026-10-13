## 1. Failing test

- [x] 1.1 Add a test (skipped without `OGR_AVAILABLE`): a polygon question with a bow-tie answer and
      a square answer; `?format=kml` returns 200 and both placemarks carry geometry. Confirm it fails
      on the unmodified code (exit 1 or an empty placemark, depending on GDAL).
      Done: on unmodified code ogr2ogr stopped with `ERROR 6: Invalid polygon` → `ExportFailed`; GPKG test passed.

## 2. Fix

- [x] 2.1 `survey/export.py::write_ogr`: pass `-makevalid` in the KML branch.
- [x] 2.2 Run the export tests (all 13 `*Export*` classes in `survey/tests.py`, 73 tests): green.

## 3. Ship

- [x] 3.1 PR referencing #277; after merge, resolve the PostHog issue.
