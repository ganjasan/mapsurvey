# Excel (.xlsx) export with coordinates

**Type**: feature
**Priority**: medium
**Area**: backend
**Created**: 2026-08-31

## Description

Every competitor lists "Excel export" and buyers read "CSV" as "not Excel". Our CSV opens
in Excel, but with the locale comma trap (`52,52`), UTF-8 BOM questions, and no column
widths or sheet per question. A real `.xlsx` with one sheet for answers, one for sessions,
and lon/lat columns for geo answers removes a demo objection for the cost of `openpyxl`.

## Scope Sketch

- Add `.xlsx` to the download ZIP next to CSV (same session filter, same clean-export
  rules from data-management).
- Sheets: `responses` (one row per session, one column per question, sub-questions
  flattened as `question.sub`), `sessions` (status, start, source/UTM), `geo` (one row per
  feature: session, question, WKT + lon/lat centroid).
- Dates as real Excel dates, numbers as numbers — not strings.

## Notes

Keeps Free (export is never gated). Pairs with `#8` Shapefile/GeoPackage.
