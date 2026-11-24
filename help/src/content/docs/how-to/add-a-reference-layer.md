---
title: Add a reference layer
description: Upload boundaries, sites or a plan once and show them under the respondent map on every section with a map — or only on the sections you pick.
sidebar:
  order: 12
---

You end up with a read-only layer drawn beneath respondents' answers, styled and labelled, on every section with a map or only the ones you pick, switched on from the first page.

## Before you start

- A file with the layer: GeoJSON, GeoPackage (`.gpkg`), a zipped shapefile (`.zip`), KML, or a CSV with coordinate columns. A file in another coordinate system (State Plane, UTM, British National Grid…) is converted to longitude/latitude for you; the dialog says so.
- Limits: 10 MB per file, 5,000 objects per layer, 10 layers per survey. If the file is bigger, simplify or split it; see [Layer too large](/troubleshooting/layer-too-large/).
- You must be an owner of the survey to add or remove layers. Editors can change where a layer shows.

## Steps

### Add the layer

There are two doors to the same dialog:

- In **Build**, select a section with a map. The **Map** card at the top of its panel lists what this map shows. Click **+ Layer** and choose **Upload a file**, **From Data** (a dataset of your workspace) or **Draw on the map**.
- In **Survey settings**, the **Layers used here** card has the same choices.

Pick the file. The dialog names the layer after the file and tells you how many objects it holds. Under **Where it shows**, keep **Every section with a map, now and later** — a section you add later gets the layer too — or choose **Only this section**. Give the layer a **Name respondents see**, such as `Study area` or `Proposed crossings`.

If the file is one to three areas, the dialog asks whether it is your study area. **Make it the survey's study area** turns it into the area the map opens on and can grey out the rest; see [Set the study area](/how-to/set-the-study-area/). Otherwise keep it as a reference layer.

<!-- screenshot: the Add a layer dialog after an upload, with the conversion note, the name field and the study-area question -->

### Style it

In **Survey settings › Layers used here**, open the layer with the pencil:

1. Under **Style**, set the **Colour**, **Opacity**, **Line width** and, for point layers, **Point size** and **Point icon**. If the file already carries simplestyle properties (`stroke`, `fill`, `marker-color` and so on), those win over the layer colour.
2. To colour features by one of their properties, switch on **Style by attribute**, pick the **Property** and a **Mode**: **Categories** for a text property or **Graduated** for a number. **Auto-fill from data** creates the classes for you.
3. Under **Label field**, pick the property whose value is written on each feature; leave it on **none** for no labels.
4. Switch on **Info popups** if respondents may click a feature to read its name and description.

### Change where it shows

- In a section's **Map** card, tick or untick the layer for that section. Unticking a layer that is on every section keeps it on all the others.
- In **Layers used here**, **Shows on** sets the same thing for the whole survey: **Every section with a map, now and later**, **Only these sections** (tick them) or **No map**.

Both save at once — also on a published survey, without **Publish changes**: a layer collects nothing, so respondents simply see the new map on their next page.

### Ask about each object

To ask respondents about each feature of the layer (thumbs up or down, a comment, a rating), add an **Objects on the map** question and pick the layer; add sub-questions to it. Picking the layer also puts it on that section's map if it was not there yet. See [Add sub-questions](/how-to/add-sub-questions/).

## Result

Every layer placed on a section is switched on when the section opens; respondents can switch it off in the panel's **On this map** list or the map's layers control. Sections without a map show no map. When you publish, the dialog lists every layer with where it shows and flags any layer that is on no map, with **Show on every section** and **Remove** right there.

## Where the layer lives

Each layer is a dataset in **Data**. Its page there lists the surveys and sites that use it under **Used by**; edit it in one place and every survey that uses it changes. **Remove from this survey** takes it off this survey's maps and keeps it in Data; deleting the survey keeps it too.

## Related

- [Set the study area](/how-to/set-the-study-area/)
- [Data](/how-to/data/)
- [Layer too large](/troubleshooting/layer-too-large/)
- [Add sub-questions](/how-to/add-sub-questions/)
