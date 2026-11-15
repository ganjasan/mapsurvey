---
title: Data
description: Every place dataset of your workspace in one list — the layers you uploaded or drew and the answers your surveys collect — with who uses each one.
sidebar:
  order: 80
---

**Data** lists every place dataset your workspace holds, in one place:

- **Layers** you uploaded or drew for a survey's map (bus stops, trees, project areas).
- **Shared maps** built from residents' answers.
- **Answers** to each map question of a survey — all versions of the survey together.
- **Responses** — one row per respondent of a survey.

Nothing is moved or copied to get there: the list reads the data where it already lives.

## Open the list

Choose **Data** in the left sidebar. Each row shows where the dataset comes from, how many rows it has, how many places use it (a survey, a results page, a site block) and when it last changed. Click a row to open the dataset's page; **Open the source** there takes you to where you edit or read it today — a layer in the survey's settings, answers in **Responses**.

Filter by source (Layer, Shared map, Answers, Responses) or by privacy, or search by name. A filtered list is a link you can share with a colleague.

## Upload a file

Press **New dataset** and pick a file. Mapsurvey reads:

- **GeoPackage** (`.gpkg`), a **zipped shapefile** (`.zip` holding the `.shp`, `.dbf`, `.shx` and `.prj`), **KML** and **GeoJSON** — in any coordinate system the file names; Mapsurvey converts it.
- **CSV** with `latitude` and `longitude` columns, or with `easting` and `northing` columns in the British National Grid. For any other projected grid, export the file as WGS 84 first.

The file is read in the background — you can leave the page. When it is ready, a card shows how many objects were created, the coordinate system that was read, and rows that were skipped: rows without a location and repeated keys never stop the import.

Columns that look like email addresses, phone numbers or people's names are kept **private** — they never leave the dataset. A new upload is private as a whole until you decide otherwise.

Limits: 10 MB and 5,000 objects per file on Free; 50 MB and 100,000 objects on Pro.

## Describe a dataset

A dataset's page holds its **details**: name, description, theme, maintainer (the team or role that keeps it current), how often it is updated, and the licence. The licence is one of the Open Government Licence v3.0, CC BY 4.0, CC0 and Datenlizenz Deutschland – Namensnennung 2.0.

For a layer, the page also lists its **fields** — the columns of the file, or the properties of the objects you drew. For each field you can set:

- a **label** that people read instead of the raw name: `TR_HGT_M` becomes "Tree height (m)" on the object card a respondent opens and in the downloads;
- its **type** and a short **description**;
- **private** — the field stays on this page and in the object editor. No map, export, download or API shows it, and a map label or a style rule built on it is switched off while it is private.

Owners, admins and editors who work on the survey change the details; viewers read them.

## Download a layer

On a layer's page, **CSV** and **GeoJSON** download its objects with the field labels as column names. Private fields are left out.

## Privacy

Every dataset has a privacy class:

- **Public** — rows may be shown as they are. Layers you add to a survey are public, because respondents already see them on the map.
- **Aggregated** — only counts and areas may leave the workspace, with small groups hidden. Everything your surveys collect is aggregated: public results pages and site blocks show counts and grids, never a single answer.
- **Private** — workspace members only.

The list itself shows counts only. Individual answers stay in **Responses**.

## Who sees what

Workspace owners, admins and viewers see every dataset. An editor sees the datasets of the surveys they work on.

## Related

- [Add a reference layer](/how-to/add-a-reference-layer/)
- [Share results publicly](/how-to/share-results-publicly/)
- [Export responses](/how-to/export-responses/)
