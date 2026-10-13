---
title: Add sub-questions
description: Attach questions to every feature a respondent places, so each pin carries its own answers into the export.
sidebar:
  order: 11
---

You end up with a popup that opens on every placed feature, and one extra column per sub-question in your export.

## Before you start

- You need a map question (point, line, polygon or spray area) in the section. See [Add a map question](/how-to/add-a-map-question/).
- On a published survey that has responses, adding a sub-question is a structural change and happens in unpublished changes.

## Steps

1. Find the map question's card in the section's question list and click **Add Sub-question** below it. The button is only on map questions and on **Objects on the map** questions.
2. Pick a type. Sub-questions can be anything except another map question: **Choices**, **Multiple Choices**, **Text**, **Single Line Text**, **Number**, **Rating**, **Thumbs up / down**, a photo and so on.
3. Under **Name**, write a short, distinctive label. This name becomes the column heading in the spreadsheet and the attribute name in GeoJSON and GeoPackage, so `Reason` or `Severity` reads better in QGIS than a full sentence. If you need the full sentence for respondents, put it in **Subtext**.
4. For a **Choices** sub-question, add the options under **Choices**. Each option has a **Code** (a number that lands in the export) and a **Name** (what respondents see). Keep codes stable once responses start arriving.
5. Click **Create**. Repeat for each sub-question; two or three per feature is plenty.

<!-- screenshot: a point question card with two sub-questions nested under it and the Add Sub-question button below -->

6. Check it in the **Live preview**: place a feature, answer the popup and click **Apply**. Clicking the feature again reopens the popup for editing or deleting.

## Why the names matter

Mapsurvey exports every map question as one layer and every sub-question as one attribute of that layer:

- In the **GeoJSON + CSV** archive, each feature's `properties` hold the sub-question answers keyed by name.
- In **Excel** and **CSV**, the `observations` table has one row per placed feature and one column per distinct sub-question name across all map questions. Two map questions that both have a sub-question called `Quantity` share one `Quantity` column; two that call it `Quantity` and `How many?` get two columns. Reuse names deliberately when the questions mean the same thing.
- In **GeoPackage** and **Shapefile**, the names become field names. Shapefile cuts them to 10 characters, which is one reason to prefer GeoPackage.

A **Choices** sub-question exports its code and name consistently; free text exports whatever was typed. Choice answers are safer than free text when you plan to count or style by the answer.

## Result

Respondents who place a feature see the popup, answer, and return to the question list. A sub-question left blank exports as an empty cell; it never borrows another question's value. The **Responses › Map** shows the sub-question answers when you click a feature, and every export carries them next to the geometry.

## Related

- [Add a map question](/how-to/add-a-map-question/)
- [Exports](/reference/exports/) — column order and file layout for every format.
- [Export responses](/how-to/export-responses/)
