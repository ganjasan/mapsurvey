---
title: Add a map question
description: Add a point question to "Safe crossings", attach sub-questions to every pin and check it in the preview.
sidebar:
  order: 2
---

By the end of this page respondents can drop a pin where they feel unsafe crossing the street and answer two short questions about that spot.

## Add the point question

1. In the section you set up, click **New Question**.
2. In the type picker, look under **Map questions** and choose **Geo Point**. A point is the right choice here: respondents place pins about twice as often as they draw shapes, and a crossing is a place, not an area.
3. Under **Name**, type `Where do you feel unsafe crossing the street?`. This is the text on the draw button respondents tap.
4. Under **Subtext**, add one line of help, for example `Tap the map on the crossing. You can add several.`
5. Tick **Required** if every respondent must place at least one pin. Leave it off for a first survey; a respondent who has no unsafe crossing in mind should still be able to finish.
6. Under **Places per respondent**, leave **Min** and **Max** empty. One point question collects as many pins as a respondent wants, and they all land in one layer when you export.
7. Click **Create**.

<!-- screenshot: the question dialog with Geo Point selected, the name filled in and Places per respondent visible -->

The question now appears in the section's list with a type badge, and the **Live preview** shows a **Place point** button.

## Attach sub-questions to the pin

A pin on its own tells you where, not why. Sub-questions open in a popup on every pin the respondent places, and each one becomes a column in your export next to that pin's coordinates.

1. On the question's card, click **Add Sub-question**.
2. Choose **Choices**, name it `What makes this crossing unsafe?`, and add options under **Choices**: `Fast traffic`, `Poor visibility`, `No crossing marked`, `Long wait at the signal`. Tick **Other** if you want a free-text escape. Click **Create**.
3. Click **Add Sub-question** again. Choose **Text**, name it `Anything else about this spot?` and click **Create**.

Sub-questions cannot be map questions themselves, and the picker does not offer those types here.

Keep sub-question names short and distinctive. The name is the column heading in the spreadsheet and the attribute name in the GeoJSON, so `Reason` reads better in QGIS than a full sentence. Choice sub-questions export cleaner than free text; see [Add sub-questions](/how-to/add-sub-questions/).

<!-- screenshot: the point question card with two sub-questions nested under it -->

## Try it in the preview

The **Live preview** on the right is a working copy of the section, with submission switched off.

1. Click **Place point** in the preview, then tap the map. On a phone the map shows a crosshair; move the map under it and confirm.
2. The popup opens with your two sub-questions. Answer them and click **Apply**.
3. The pin stays on the map, the draw button shows a counter of 1, and its subtitle invites another pin. Click the pin to edit or delete it.

If something reads wrong, edit the question (the pencil icon on its card) and the preview refreshes.

For a larger view, use **Preview** › **Survey — as respondent** in the top navigation; it opens the whole survey in a new tab.

## Add a question that is not on the map

Most surveys end with a question or two about the respondent. Click **New Question** and pick **Choices** or **Text** from the **Questions** group; these render in the panel beside the map rather than in a popup. If you want a page with no map at all, add a **New Section** and set its **Layout** to **Form**.

Other map question types (lines, polygons, spray areas) are covered in [Add a map question](/how-to/add-a-map-question/) and compared in [Question types](/reference/question-types/).

## Next

[Publish and share](/start-here/publish-and-share/) — open the survey and get the link.
