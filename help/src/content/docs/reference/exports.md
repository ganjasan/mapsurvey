---
title: Exports
description: Every format the Export data dialog produces, the tables and layers inside each, and the three switches that change what is included.
sidebar:
  order: 20
---

**Export data** opens one dialog from the Responses page and from a survey card's **…** menu. You choose a format, a version scope and up to three switches; the export then downloads as a link, so the same export can be repeated later by opening the same address. The last format you chose is remembered in your browser.

The data export is not the survey backup. **Backup (survey file)** on the survey card produces the survey definition for import into another Mapsurvey; it contains no responses.

For the procedure, see [Export responses](/how-to/export-responses/). Exporting needs the **viewer** role or higher on the survey.

## Formats

| Format | File | Contents | Made for |
|---|---|---|---|
| **Excel** | `.xlsx` | Sheets `observations`, `responses`, `sessions`, plus one `objects_<code>` sheet per **Objects on the map** question with sub-questions. Header row bold and frozen; datetimes are Excel datetimes in UTC; numbers and `lat`/`lon` are numeric | Excel, Google Sheets, LibreOffice |
| **GeoPackage** (recommended for GIS) | `.gpkg` | One layer per map question, named after the question, with every attribute, plus one layer per **Objects on the map** results file | QGIS, ArcGIS |
| **Shapefile** | `.zip` | Per map question: `.shp`, `.shx`, `.dbf`, `.prj` (WGS 84) and `.cpg` (UTF-8). Field names longer than 10 characters are shortened — prefer GeoPackage | Legacy GIS |
| **GeoJSON + CSV** | `.zip` | One `<question>.geojson` per map question, one `<survey>.csv` with the other answers (one row per respondent), `objects_<code>.csv` and `layers/<layer>.results.geojson` for objects questions, and every attached file under `files/`. This is the original export; its layout does not change | Scripts and older workflows |
| **KML** | `.kml` | One folder per map question; sub-question answers as feature data. Invalid polygons are repaired for KML only | Google Earth |
| **CSV** | `.zip` | The same tables as Excel — `observations.csv`, `responses.csv`, `sessions.csv`, `objects_<code>.csv` — as UTF-8 with BOM, comma-separated, `.` decimal, ISO 8601 datetimes | Any spreadsheet or script |

GeoPackage, Shapefile and KML appear only when the server has the GDAL `ogr2ogr` tool (mapsurvey.org has it; a self-hosted server may not).

All geometry is WGS 84 (EPSG:4326). Every format is written from the same collected data, so the tables never disagree with the GeoJSON.

## Tables

### observations — one row per placed feature

Columns, in order:

| Column | Meaning |
|---|---|
| `session_id` | The respondent's session |
| `session_start_utc` | When they started |
| `session_language` | The language they answered in |
| `validation_status` | `approved`, `not_approved`, `on_hold` or empty |
| `version` | The survey version the answer belongs to |
| `section`, `question`, `question_code` | Where the feature was drawn |
| `geometry_type` | `Point`, `LineString`, `Polygon` or `MultiPoint` (spray area) |
| `lat`, `lon` | The point, or the centroid of a line, polygon or spray cloud |
| `wkt` | The full geometry as well-known text |
| one column per sub-question **name** | Sub-questions with the same name on different map questions share one column; `question` tells them apart. A ranking sub-question is one column per item; an **Other…** write-in adds a column |
| `mark_key`, `votes_up`, `votes_down`, `comments` | Only when the survey has a shared map: what other respondents said about this mark |
| `dot_count`, `area_m2` | Only when the survey has a spray area question |

A blank sub-question stays blank; it never inherits another feature's value.

### responses — one row per respondent

Every non-map answer, one column per question (a ranking question is one column per item, a file question lists archive paths), then `session`, `session_id`, `session_start_utc`, `language` and `validation_status`. This is the same layout as the CSV inside the GeoJSON + CSV archive, with the start column named for what it is.

### sessions — one row per respondent

`session_id`, `session_start_utc`, `session_end_utc`, `language`, `validation_status`, `opened_by_kind` (`external`, `owner`, `collaborator` or `preview`), `version`, `tags`, `notes`.

### objects_<code> — one row per respondent per object

For each **Objects on the map** question that has sub-questions: `session_id`, `object_key`, `object_title`, `object_category`, one column per sub-question, `datetime`, `language`, `validation_status` and, for a shared map, the object's moderation `status`.

### GeoJSON layers

Each map question is a FeatureCollection named after the question. Every feature carries its sub-question answers (one property per sub-question, present even when empty), `session`, `session_id`, `language`, `validation_status`, shared-map verdicts when present and, for a spray cloud, `dot_count` and `area_m2`.

## Options in the dialog

| Option | Default | Effect |
|---|---|---|
| **Version** | the current version | Shown only when the survey has published more than one version. **All versions** prefixes every file with `v<n>_` and adds a `version` column |
| **Include excluded responses** | off | Adds trashed and not-approved responses |
| **Completed responses only** | off | Keeps respondents who answered the last section — the same count as "completed" on the Responses overview |
| **Include attached files** | off | Shown only when the survey has photo, audio or document questions. Adds the uploads under `files/<session>/`; Excel, GeoPackage and KML then download as a ZIP with the file next to the `files/` folder. GeoJSON + CSV always includes files |

Sessions where nobody answered anything are never exported, whatever the switches say.

## For scripts

Every export is a `GET` to `/surveys/<uuid>/download` with `format=zip|xlsx|csv|gpkg|shp|kml` (no `format` = GeoJSON + CSV), and the optional `version`, `include_all=1`, `completed_only=1` and `files=1`. The dialog shows the address it builds; copy it to repeat the export. The request must be signed in with a role on the survey.

## Related

- [Export responses](/how-to/export-responses/)
- [Question types](/reference/question-types/)
- [Edit a published survey](/how-to/edit-a-published-survey/) — what a version is
