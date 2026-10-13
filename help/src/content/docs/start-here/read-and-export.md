---
title: Read responses and export
description: Watch "Safe crossings" responses arrive on the Responses page, then export them as GeoJSON, Excel or GeoPackage and open them in QGIS.
sidebar:
  order: 4
---

By the end of this page you have looked at the first responses on a map and have a file open in QGIS with one row per pin and the sub-question answers as attributes.

## Open the Responses page

Click the **Responses** tab in the editor's top navigation. It has five views:

- **Overview** — counts for the survey: responses, responses today, completion rate, median time, map features and flagged responses, plus a small **Response Map** and **Latest responses**. Until the first respondent finishes, it tells you to share the link.
- **Map** — every pin, line and polygon from every respondent on one map. Click a feature to see the answers attached to it.
- **Responses** — one row per respondent. Clicking a row opens the response drawer with everything that person answered, where you can add tags and notes or exclude a response you think is spam.
- **Charts** — one chart per choice, rating and number question. Clicking a bar filters the map and the table to those respondents.
- **Performance** — how many started each section and where people dropped out.

<!-- screenshot: the Responses › Map view with a cluster of pins on the street and one popup open -->

Responses collected through the test link before you published are not here if you ticked **Delete all test responses** when publishing.

## Export the data

1. On any Responses view, click **Export data**.
2. Choose a **Format**:

   | Format | Contents | Use it for |
   |---|---|---|
   | **GeoJSON + CSV** | A ZIP with one GeoJSON per map question and a CSV of the other answers, one row per respondent | Any GIS; web maps; scripts |
   | **Excel** | One workbook: `observations` (one row per placed feature, with latitude and longitude), `responses` (one row per respondent), `sessions` | Reading in Excel, Google Sheets or LibreOffice |
   | **GeoPackage** | One `.gpkg` file, one layer per map question, every attribute kept | QGIS and ArcGIS (recommended) |
   | **CSV** | The same tables as Excel, as UTF-8 CSV files in a ZIP | R, Python, pandas |
   | **Shapefile** | One shapefile per map question in a ZIP; field names are cut to 10 characters | Older GIS tools |
   | **KML** | One file, one folder per map question | Google Earth |

3. Leave **Include excluded responses** off unless you want responses you trashed or marked as not approved.
4. Switch on **Completed responses only** to export only respondents who reached the last section; the count matches **completed** on the Overview.
5. Click **Export**. The browser downloads the file.

The dialog remembers your last format. Respondents who opened the survey but answered nothing are never exported. Every detail of each format, including column names, is in [Exports](/reference/exports/).

## Open the result in QGIS

For "Safe crossings" the GeoPackage is the straightforward choice:

1. In QGIS, choose **Layer › Add Layer › Add Vector Layer…**, pick the `.gpkg` file and add the layer named after your point question. Dragging the file from the file manager onto the map canvas does the same.
2. Open the attribute table. Each row is one pin. Four columns identify the response (`session`, `session_id`, `language`, `validation_status`); the remaining columns carry the sub-question answers under the names you gave them, so `What makes this crossing unsafe?` is the reason column.

3. Style the layer by that reason column (**Categorized** in the layer's symbology) and you have a map of unsafe crossings coloured by cause.

Coordinates are WGS 84 (EPSG:4326). If your project uses a projected system, QGIS reprojects on the fly.

If you chose **GeoJSON + CSV** instead, unzip the archive and add the `.geojson` file the same way; the `.csv` holds the non-map answers with the same `session_id`, so you can join the two tables on it.

## Where to go from here

- Give respondents and stakeholders a live view with a public results page: [Share results publicly](/how-to/share-results-publicly/).
- Add boundaries, a plan or existing sites beneath the respondent map: [Add a reference layer](/how-to/add-a-reference-layer/).
- Change the survey while it is live: [Edit a published survey](/how-to/edit-a-published-survey/).
- Think about what makes a map question work before the next survey: [Designing a map survey](/learn/designing-a-map-survey/).
