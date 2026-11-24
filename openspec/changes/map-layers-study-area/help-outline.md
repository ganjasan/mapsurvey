# Help outline — map-layers-study-area

Written in task 0.3; the pages themselves are task 8.2. Paths are under
`help/src/content/docs/`; registry keys in `survey/help_links.py` (`HelpLinksTest` checks them).

## 1. `how-to/add-a-reference-layer.md` — rewritten (key `reference_layers`, path unchanged)

Promise: "A read-only layer under the respondents' answers, on every map section or only the ones
you pick, switched on from the first page."

- **Before you start** — formats (GeoPackage, zipped shapefile, KML, GeoJSON, CSV with coordinate
  columns); projected files are converted to WGS 84 (no more "reproject first"); limits 10 MB /
  5,000 objects / 10 layers; `editor` role or above.
- **Add the layer** — two doors, same dialog:
  - the section's **Map** card in Build → **+ Layer** → *Upload a file* / *From Data* / *Draw on
    the map*;
  - **Survey settings** → **Layers used here** → **+ Layer**.
  The dialog: file recognised, "coordinates converted" note, name, "looks like a boundary — make it
  the study area?" (links to page 2), **Where it shows**: *Every section with a map, now and later*
  (default) / *Only these sections*.
- **Style it** — unchanged steps (colour, opacity, width, point icon, style by attribute, label
  field, key field, info popups), opened from the layer row.
- **Change where it shows** — scope in the Map card or Layers used here; saves at once, also on a
  published survey (no "Publish changes").
- **Ask about each object** — the *Objects on the map* question only when respondents answer about
  objects; picking a layer there also puts it on that section. Link to Add sub-questions.
- **Result** — every placed layer is switched on when a section opens; respondents can switch it
  off; sections without a map show no map. The publish check lists layers that are on no map.
- **Where the layer lives** — it is a dataset in **Data** ("Used by" names the survey); edit it
  there and every survey that uses it changes; *Remove from this survey* keeps it in Data;
  deleting the survey keeps it too.
- Related: Set the study area (new), Data, Layer too large, Add sub-questions.

Removed: "Show it on a section" via a question, "In the panel: list or legend", "a layer can be
shown once per section".

## 2. `how-to/set-the-study-area.md` — new (key `study_area`)

Promise: "The map opens on your area, the rest is greyed out, and — if you want — nobody can put an
answer outside it."

- **Before you start** — one study area per survey; it is not a layer; `editor` role or above.
- **Find it by name** — Map card → **Study area** → *Set*; type a place ("Midtown, Atlanta"); pick
  one of up to five OpenStreetMap results (name, type, size).
  - A street, river or rail line becomes a corridor — choose 50, 100 or 200 m.
  - A place OpenStreetMap knows only as a point starts as a rectangle — move its corners.
  - Nothing found / service unavailable — upload, use a layer, or draw.
- **Adjust the outline** — drag, add, remove vertices; *Done* saves; © OpenStreetMap contributors.
- **Other sources** — upload a file (same formats and conversion as layers), use a polygon layer of
  the survey, draw from scratch.
- **Fog outside** — on by default; what respondents see (map opens on the area, grey outside,
  they can still pan).
- **Answers outside** — *Allowed* (default) / *Not allowed*; the message respondents see and how
  to translate it (Translations tab); lines and areas get 5 m tolerance; spray is clipped.
- **Where else it shows** — the printed form frames it; the Responses map and Reports map blocks
  draw its outline (*Study area outline* switch per block).
- **Change or remove it** — editing on a published survey applies at once; answers already given
  are not re-checked.
- Related: Add a reference layer, Print a paper form, Reports.

## 3. Small edits

- `reference/question-types.md` — *Objects on the map*: "asks about objects of a layer"; no
  legend/list mode.
- `how-to/lay-out-a-section.md` — layers and the study area are in the section's Map card.
- `how-to/print-a-paper-form.md` — the frame follows the study area.
- `faq.md` — "Why is my layer not on the map?" → the publish check and *Where it shows*.
- `troubleshooting/import-failed.md` — projected files are converted, not refused.
- Screenshots: Map card, Add layer dialog, study area editor (place results + corridor width),
  respondent phone with fog.
