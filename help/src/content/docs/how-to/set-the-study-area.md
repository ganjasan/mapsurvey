---
title: Set the study area
description: Tell the survey which area it is about — the map opens on it, the rest is greyed out, and, if you want, nobody can put an answer outside it.
sidebar:
  order: 13
---

You end up with a study area for the survey: the respondent map opens on it, the outside is greyed out, and — when you switch it on — a mark placed outside is not taken. A section with a map can use the survey's area, an area of its own, or none.

## Before you start

- A survey has one study area, set in **Survey settings**. It is not a layer: it frames the maps rather than drawing objects on them.
- A section with a map can override it on its **Map** card: [an area of its own, or none](#a-different-area-on-one-section).
- You need the **editor** role or higher on the survey.

## Steps

### From the survey wizard

When you start a survey with the wizard and your description names a place, the wizard sets the study area for you.

1. Write what you want to find out, for example `Snow clearing in Saint Petersburg`. The map moves to the place and a **Study area** strip appears under it with the place's boundary and grey outside.
2. Keep it, or use the strip:
   - **Edit outline** — move the edge on the map. A large boundary is simplified to a few dozen corners first. Click **Done** when finished.
   - **Corridor width** — for a street, 50 m, 100 m or 200 m.
   - **Map answers outside** — **Allowed** (the default) or **Not allowed**.
   - **Remove** — the survey starts without a study area. **Use the boundary of …** brings it back.
3. Draft the survey. If the boundary had not loaded yet, the wizard looks it up from the place in your description. If none is found, the survey starts without one; set it later as below.

### Find it by name

1. Open **Survey settings**. In the **Respondent map** card, next to **Study area**, click **Set** (or **Edit** when the survey has one).
2. Type the place, for example `Midtown, Atlanta`, and click **Find**. Up to five matches from OpenStreetMap appear with their type.
3. Click the one you mean. Its outline opens on the map, ready to adjust.
   - A **street, river or rail line** becomes a corridor along it. Choose its width: **50 m**, **100 m** or **200 m**. If OpenStreetMap holds the street as several pieces, you get the piece you picked; extend it by moving corners.
   - A place OpenStreetMap knows only as a **point** starts as a rectangle around it.
   - If nothing fits, or OpenStreetMap does not answer, use one of the other ways below.

### Adjust the outline

Drag a corner to move it, drag a middle handle to add a corner, click a corner to remove it. Nothing is saved until you click **Save**. Boundaries come from © OpenStreetMap contributors.

<!-- screenshot: the study area editor with the place results, the corridor width buttons and the outline in vertex editing -->

### Other ways in

- **Upload a boundary file** — GeoJSON, GeoPackage, a zipped shapefile or KML; any coordinate system is converted.
- **Use a layer of this survey** — any of its polygon layers.
- **Draw it on the map** — click corners, then the first one again to close the area.

### What respondents see

- **Grey out the map outside** is on by default. The map opens on the area; respondents can still move around.
- **Map answers outside the area**: **Allowed** (default) or **Not allowed — the mark is not placed**. With **Not allowed**, write the **Message respondents see**, for example "Please place your answer inside Midtown." Lines and areas may touch the edge: a corner up to 5 m outside still counts as inside. A spray keeps only its dots inside. Translate the message in the **Translations** tab.

The two switches — **Grey out the map outside** and **Refuse map answers outside** — are also in **Survey settings → Respondent map**, next to **Remove**. The message stays in the editor.

### A different area on one section

A survey about a whole city can ask about one street on its second page, and a "Where do you live?" page should accept marks anywhere.

1. In **Build**, select the section. In its **Map** card, under **Study area**, choose:
   - **Survey's area** — the default: the section uses the survey's area.
   - **Own area** — the editor opens for this section, starting from the survey's outline. Find a place, adjust the outline, set its fog, its rule and its message, and click **Save**. The survey's area does not change.
   - **No area** — no grey outside and no refusal on this section.
2. The choice saves at once. Switching away from **Own area** keeps its outline: choose **Own area** again to get it back. To change it later, click **Edit** next to **Own area**.

The Live preview, the respondent map, the refusal of answers outside and the printed form follow each section's choice; when a respondent moves to a section with another area, the map moves to it. An own area's message is translated in the **Translations** tab like the survey's.

## Result

The map opens on the area on every section with a map that uses it (a section whose own start lies inside the area keeps it). The printed form is framed on each section's area too, and the **Responses** map and **Reports** map blocks draw the survey's outline — switch it off for one block with **Study area outline** in the block's panel.

Changing or removing the study area on a published survey applies at once. Answers already given are not checked again.

## Related

- [Add a reference layer](/how-to/add-a-reference-layer/)
- [Print a paper form](/how-to/print-a-paper-form/)
- [Translate a survey](/how-to/translate-a-survey/)
