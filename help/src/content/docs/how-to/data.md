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

## Use a dataset in a survey or on a site

A layer in Data can be shown in several places without uploading it again. It is **linked, not copied**: when the dataset changes, every survey and site that shows it changes too.

- **In a survey**: in the survey's settings, the **Reference layers** card has **From Data**. Pick the dataset and press **Add**. The layer appears in the list marked *From Data*; choose which fields its object card shows, or **Unlink** it. Its colour, style and objects are edited in Data, for every place at once.
- **On a site**: in a **Map** block, **Show** picks the dataset instead of an uploaded area.

Only a **public** dataset can be linked — a new upload is private until you switch **Access** to *Public* on its page. A linked dataset stays public until you unlink it everywhere. A survey map takes up to 5,000 objects and 10 MB per layer, and up to 10 layers.

The dataset's page lists everything that uses it under **Used by**: the survey it belongs to, the surveys and sites that link it, and the questions that show it.

## Group an engagement with tags

An engagement is usually a survey, a site and a few datasets. **Tags** keep them together: type them on a dataset's page (under the details) and in a survey's settings panel, separated by commas — "Riverside plan 2027", "Parks". A tag is created the first time you use it and disappears when nothing carries it any more.

The **Data** list and the survey dashboard show each item's tags; click a tag to see only what carries it, and the dashboard search finds tags too. Over the API and MCP, a survey's tags come with it, `GET /api/v1/surveys?tag=…` filters by one and `PUT /api/v1/surveys/{uuid}/tags` (or the `set_survey_tags` tool) sets them.

## Save a view

A **view** is a saved selection of a dataset that keeps its name: "Trees in poor condition", "Answers to *Where would you plant a tree?* as counts". Surveys and site map blocks can show a view instead of the whole dataset, and it follows every new version of the dataset.

- On a **layer**, open **New view** under **Views**: give it a name and a colour, add up to three conditions (a field *is*, *is one of*, *greater than* or *less than* a value) and tick the fields it keeps. Only public fields can be used.
- On the **answers** to a map question, a view is always a grid, never anyone's own mark. Choose what a cell says under **What it shows**:
  - **Grid of counts** — how many respondents marked the cell.
  - **Coverage** (routes and areas) — how many respondents drew over the cell, and their share of everyone who drew.
  - **Density** (places and spray) — how many marks fall inside the cell.

  A cell with fewer respondents than the privacy threshold is left out, however many marks it holds. These views can be shown in a site's **Map** block, not as a survey layer.
- On a survey's **responses**, a view computes a table:
  - **Engagement** — how many people opened the survey, answered at least one question and finished it, in total and per day, week or month.
  - **Cross-tab** — two choice, rating or thumbs questions against each other: how many respondents gave each pair of answers, among those who answered both. Pick the question for the rows and the one for the columns.

  Open **Preview** next to a view to see its result exactly as a report will show it. A count under the threshold reads "<3" and its value is never sent, also over the API; the totals of that row and column, and the number of respondents who answered both, then read "—", because they would give the count away.
- A **Responses filter** is saved on the Responses page, not here: filter the table, open **Views** in its toolbar and name the filter. It is listed with the survey's responses, and **Open in Responses** applies it again. It names questions by their code, so it keeps working after you publish changes; a filter on an answer option matches the option's wording, as the table does.

Pick a view in a survey's **From Data** list or a site's **Map** block — it appears as *Dataset › View*. A view that is shown somewhere cannot be deleted until it is unlinked there.

## Upload a new version

When the data changes — the trees were re-inspected, the bus stops moved — press **Upload new version** on the dataset's page and pick the new file. Rows are matched to the dataset's objects on its **key column** (an ID per row, such as `TREE_ID`), so the dataset needs one: a file uploaded without an ID column needs a new upload instead.

Before anything is saved, the page shows how many objects will be **added**, **changed**, **removed** and left **unchanged**, and how many answers hang on the objects that would be removed. Write what changed and press **Apply version**, or **Discard** it.

Objects whose key stays are updated in place: answers residents gave about them stay attached. Every survey and site that shows the dataset shows the new version at once. The **Versions** list keeps the date, author, note and counts of each one.

## Delete a dataset

**Delete dataset** on the page of a dataset you uploaded first lists every place that uses it. Surveys and sites stop showing it once you confirm. While an "Objects on the map" question shows it, the delete waits: remove the question or pick another layer for it first. A layer that belongs to a survey is deleted in that survey's settings.

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
