---
title: Export responses
description: Download responses as GeoPackage, Excel, CSV, Shapefile, KML or GeoJSON + CSV, and open them in QGIS or Excel.
sidebar:
  order: 70
---

You end up with a file of every response — map answers as GIS layers, everything else as tables — on your computer.

## Before you start

- You have the **viewer** role or higher on the survey.
- For GIS use, QGIS or ArcGIS is installed; for tables, Excel, Google Sheets or LibreOffice.

## Steps

1. Open the survey's **Responses** page and press **Export data**. The same dialog opens from the **…** menu on the survey card on your dashboard.
   <!-- screenshot: the Export data dialog with the format list -->
2. Pick a **Format**:
   - **GeoPackage** for QGIS or ArcGIS — one file, one layer per map question, every attribute kept.
   - **Excel** for a spreadsheet — sheets `observations` (one row per placed feature, with `lat`/`lon`), `responses` (one row per respondent) and `sessions`.
   - **GeoJSON + CSV** if a script or an older workflow expects it; **Shapefile**, **KML** or **CSV** for other tools. See [Exports](/reference/exports/) for what each contains.
3. If the survey has published more than one version, choose a **Version**: the current one, a past one, or **All versions**.
4. Switch on what you need:
   - **Include excluded responses** to add trashed and not-approved responses.
   - **Completed responses only** to keep only respondents who reached the last section — the same number as "completed" on the Overview.
   - **Include attached files** (shown when the survey has photo, audio or document questions) to add the uploads; Excel, GeoPackage and KML then arrive as a ZIP with the file next to a `files/` folder.
5. Press **Export**. The download starts; the address shown under the switches is the export itself — copy it to repeat the same export later.

## Open the result

**In QGIS** — drag the `.gpkg` onto the map and choose the layers to add; each map question is one layer with the sub-question answers as fields. For a GeoJSON + CSV ZIP, unzip it and drag each `.geojson` onto the map. Coordinates are WGS 84 (EPSG:4326). Attached files are referenced by their path inside the archive.

**In Excel** — open the `.xlsx`. `observations` is the sheet for anything spatial: filter by `question`, sort by a sub-question column, or plot `lat`/`lon`. `responses` has one row per respondent for everything that was not drawn. For a CSV ZIP, each table is a UTF-8 file that Excel opens without an import wizard.

## Result

A file named after the survey with every non-empty response in the chosen scope. Sessions where nobody answered anything are never exported.

## Related

- [Exports](/reference/exports/) — every column and file explained
- [Question types](/reference/question-types/) — how each type is stored
- [Edit a published survey](/how-to/edit-a-published-survey/) — where versions come from
