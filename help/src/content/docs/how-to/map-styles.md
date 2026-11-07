---
title: Map styles
description: The base maps under your surveys — the five presets, your own copies of them, and how to pick one in a survey.
sidebar:
  order: 78
---

Every survey map, online and on the printed form, sits on a **map style**. Your workspace's styles live in one place, **Map styles** in the sidebar under *Library*, and any of them can be picked in any survey.

## What is there

- **Streets**, **Satellite**, **Topo** — the general-purpose base maps.
- **Paper A** — a clean street map made for printing: white ground, cased streets with names, no shop icons, city names only when zoomed out. A pen mark stays visible on a greyscale copy.
- **Paper B** — the planner's map: white streets, bold street names, light-green parks, teal water.
- **Your styles** — copies you made, under your own names.

Each card shows a piece of the map around your newest survey and how many of your surveys use the style.

## Pick a style for a survey

1. Open the survey's **Settings** and find **Base maps**.
2. Tick the styles respondents may switch between and choose the **Default base map**.
3. A single section can use a different base map: open the section's map picker and set **Override base map**.

The printed form uses the same style as the section it prints.

## Make your own

1. Press **Duplicate** on Streets, Paper A or Paper B. (Satellite and Topo cannot be duplicated.)
2. The copy appears as *Publishing…* for a few seconds while its hosted map is created, then it is ready to pick in survey settings.
3. Press **Edit** on the copy to change how it looks.

Creating and editing styles is a **Pro** feature; the trial includes two styles. Using a style that already exists — a preset or your own — never needs Pro, so a survey keeps its map if a subscription lapses.

## Edit a style

The editor shows the controls on the left and the map on the right, framed at one of your surveys (pick another in the dropdown above the map).

- **What stays on the map** — place icons and names, footpaths, route shields and arrows, relief and ferries, regional boundaries, buildings. Untick what a paper map does without.
- **Colours** — land, parks, water, national borders, street and city names, water and district names. Pick a swatch or type a colour like `#dcefd2`. A warning under a colour means it is hard to tell apart from the land on a photocopy.
- **Roads and labels** — the road look (light, medium, strong), bold street names, the zoom up to which city and region names show, and **Greyscale** for a map that is black and white from the start.

Every change repaints the map at once. Press **Save** to publish the new version; it takes a few seconds and the name field saves with it. The **Print** tab shows the last published version as the printed form renders it; tick **As a photocopy** to see it in greyscale.

A survey that is already published keeps the version it was published with until you publish it again; drafts and the editor preview always use the newest one.

## Export and import a style

**Export** on a card downloads the style as one small JSON file; **Import a style** at the top of the page reads such a file into this workspace and publishes it like a copy. That is how a house style travels between your workspaces — or to a colleague's.

The file carries only the style itself:

```json
{
  "format": "mapsurvey-map-style",
  "version": 1,
  "name": "House style",
  "base": "mapbox/streets-v12",
  "settings": { "poi": false, "park": "#cfe6b8", "water": "#2f8f86" }
}
```

No identifiers of your account or workspace are in it. On import the settings go through the same controls the editor has, so a file cannot do more than the editor can; a name already in the library gets a number after it. Importing counts as creating a style (a **Pro** feature); exporting needs Pro too.

## Delete a style

**Delete** works only when no survey uses the style. If one does, the message names it: choose another base map there first.

## Still stuck?

Write to us from the **?** menu.
