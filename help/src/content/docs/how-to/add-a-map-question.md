---
title: Add a map question
description: Add a point, line, polygon or spray-area question, limit how many features a respondent may place, and make it required.
sidebar:
  order: 10
---

You end up with a question that collects geometry on the section's map, with the number of features per respondent under your control.

## Before you start

- The section's **Layout** must be **Map**. Map questions are not offered in a **Form** section.
- If the survey is published and already collecting responses, adding a question happens in unpublished changes; see [Edit a published survey](/how-to/edit-a-published-survey/).

## Steps

1. Select the section in the left column and click **New Question**.
2. In the type picker, choose one of the types under **Map questions**:

   | Type | Respondent does | Ask it when |
   |---|---|---|
   | **Geo Point** | Taps the map to drop a marker | The answer is a place: a crossing, a bench, an incident |
   | **Geo Line** | Draws a route by placing vertices | The answer is a path: a walk to school, a cycling route |
   | **Geo Polygon** | Outlines an area vertex by vertex | The area has edges a respondent could trace: a plot, a block, a site |
   | **Spray area** | Paints a fuzzy cloud with a brush | The area has no honest boundary: where the centre ends, where it feels unsafe |

   Points get answered about twice as often as polygons, because drawing costs effort. When in doubt, ask for a point.
3. Under **Name**, write the question as respondents should read it on the draw button, for example `Where do you feel unsafe crossing the street?`
4. Under **Subtext**, add one line of instruction. For a spray area, tell respondents that density means confidence: "spray thicker where you are certain".
5. Pick a **Color** and, for points, an icon under **Icon class**. These are what the respondent's markers look like; they also tell different map questions apart on the **Responses › Map**.
6. Tick **Required** if every respondent must place at least one feature before moving on. A required map question that is never answered blocks the section, so use it only when the survey is pointless without that answer.
7. For a point, line or polygon, set **Places per respondent**:
   - **Min** is the smallest number of features a respondent must place to move forward. Leave it empty (or 0) for optional.
   - **Max** is the ceiling. When a respondent reaches it, the draw button is disabled until they delete a feature. Leave it empty for unlimited.
   - A value in either field shows an "N of M marked" progress line inside the draw button.
   A spray question has no feature count: each respondent paints one cloud. Instead it offers **Brush size** (**Small**, **Medium**, **Large**) and an optional **Max dots per respondent**.
8. Click **Create**.

<!-- screenshot: the question dialog with Geo Point chosen and Places per respondent Min 1, Max 5 -->

## Result

The question appears in the section's question list with its type badge, and the **Live preview** shows the draw button. Place a feature in the preview to check the flow: after each feature the respondent returns to the question list and can tap the button again for the next one; a counter on the button shows how many they have placed.

All features from one question export as one layer, however many a respondent adds. Do not clone a question to collect "the 1st, 2nd, 3rd place"; use **Max** instead.

## Related

- [Add sub-questions](/how-to/add-sub-questions/) — ask something about each feature.
- [Question types](/reference/question-types/) — every type, including **Objects on the map**.
- [Writing map questions](/learn/writing-map-questions/) — wording that gets usable geometry.
