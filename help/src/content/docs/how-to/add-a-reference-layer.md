---
title: Add a reference layer
description: Upload a GeoJSON file (boundaries, sites, a plan) and show it beneath the respondent map on the sections that need it.
sidebar:
  order: 12
---

You end up with a read-only layer drawn beneath respondents' answers, styled and labelled, visible on exactly the sections you choose.

## Before you start

- A GeoJSON file in WGS 84 (longitude/latitude, EPSG:4326). Files in a projected coordinate system are rejected with a message about the coordinate system; reproject in your GIS first.
- Limits: 10 MB per file, 5,000 features per layer, 10 layers per survey. If the file is bigger, simplify or split it; see [Layer too large](/troubleshooting/layer-too-large/).
- You must be an owner of the survey to manage layers.

## Steps

### Upload the layer

1. Open **Survey settings** and scroll to the **Reference layers** card.
2. Drop the file on the upload zone, or click it to choose the file. The card now shows the layer with its feature count and size.
3. Give it a **Name** respondents will understand, such as `Study area` or `Proposed crossings`.
4. Under **Style**, set the **Colour**, **Opacity**, **Line width** and, for point layers, **Point size** and **Point icon**. If the file already carries simplestyle properties (`stroke`, `fill`, `marker-color` and so on), those win over the layer colour.
5. To colour features by one of their properties, switch on **Style by attribute**, pick the **Property** and a **Mode**: **Categories** for a text property (one class per value) or **Graduated** for a number (**Colour from → to** across **Classes** with quantile, equal-interval or manual **Breaks**). **Auto-fill from data** creates the classes for you; **Add class** adds one by hand. Tick **Show legend to respondents** so the panel explains the colours.
6. Under **Label field**, pick the property whose value is written on each feature; leave it on **none** for no labels. **Key field** names the property that makes each feature addressable; most reference layers can leave it on **none**.
7. Switch on **Info popups** if respondents may click a feature to read its name and description. Leave it off for a pure backdrop; either way the layer never intercepts a tap meant to place an answer.

<!-- screenshot: the Reference layers card with one layer, its style controls and the Label field dropdown open -->

### Show it on a section

A layer is on a section's map because a question of that section shows it. Repeat for each section that needs the layer:

1. Select the section and click **New Question**.
2. Under **Map questions**, choose **Objects on the map**.
3. Under **Layer**, pick the uploaded layer. (**Upload new…** here uploads a file without going back to settings.)
4. Under **In the panel**, choose how the layer appears beside the map: a list respondents can browse and search, or a legend line with only the name, colour and a toggle. The legend line is right for a backdrop such as boundaries.
5. Click **Create**. Add no sub-questions if the layer is only for context; without them the question collects nothing and is a display block.

A layer can be shown once per section; a second question picking the same layer is refused with the name of the question that already shows it.

## Result

The **Live preview** renders the layer beneath the map's answer geometry with your styling and labels. Respondents see it on every section that has an **Objects on the map** question for it, can switch it off in the map's layers control, and cannot select, move or edit its features. The **Reference layers** card lists the sections each layer is on. A layer that no question uses stays in the library and is shown nowhere.

To ask respondents about each feature in the layer (thumbs up or down, a comment, a rating), add sub-questions to the **Objects on the map** question; see [Question types](/reference/question-types/).

## Related

- [Layer too large](/troubleshooting/layer-too-large/)
- [Survey settings](/reference/survey-settings/)
- [Add a map question](/how-to/add-a-map-question/)
