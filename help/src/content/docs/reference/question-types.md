---
title: Question types
description: Every question and display block a survey can contain — what the respondent does, what is stored, and where the answer lands in an export.
sidebar:
  order: 10
---

The question dialog groups types the way this page does: **Questions**, **Map questions**, **Files** and **Display blocks — collect nothing**. The dialog shows some types under a friendlier name than the one stored in the survey file; both are listed.

For procedures, see [Add a map question](/how-to/add-a-map-question/), [Add sub-questions](/how-to/add-sub-questions/) and [Export responses](/how-to/export-responses/). For export file layouts, see [Exports](/reference/exports/).

## Questions

| Type | What the respondent does | Answer stored | Export column(s) |
|---|---|---|---|
| **Text** (`text`) | Types a multi-line answer. The creator can set **Min text length**. | Text | One column, the text as typed |
| **Single Line Text** (`text_line`) | Types one short line. | Text | One column |
| **Number** (`number`) | Enters a number. The creator can set **Min value** and **Max value**. | Number | One numeric column |
| **Choices** (`choice`) | Picks one option. With **Display as › Dropdown with search** the list becomes a searchable dropdown; with an **Other…** option the respondent can type their own. | One choice code | One column holding the option's name; an **Other…** write-in adds an adjacent column |
| **Multiple Choices** (`multichoice`) | Ticks any number of options; **Other…** works as above. | List of choice codes | One column, option names separated by `; ` (plus a write-in column if enabled) |
| **Range** (`range`) | Drags a slider over a numbered scale. The scale's ends come from the lowest and highest option codes; a range with no options still renders. | Number | One numeric column |
| **Rating** (`rating`) | Picks one point on a labelled scale. Rendered as a **Compact scale**, **Labeled list** or **Stars** — the survey default from **Settings › Rating questions**, or a per-question **Display as** override. | One choice code | One column holding the option's name (or its number for stars without labels) |
| **Ranking** (`ranking`) | Drags the items into order, by pointer or keyboard; every rank is used once. An incomplete or repeated order stores nothing. | The items in the respondent's order | One column per item, named `<question>: <item>`, holding that item's rank (1 = top) |
| **Date/Time** (`datetime`) | Picks a date and time. | Date and time | One column in ISO 8601 (an Excel datetime, UTC, in the `.xlsx` export) |
| **Thumbs up / down** (`thumbs`) | Taps for or against. | `up` or `down` | One column reading `up` or `down` |

Every type in this group can be **Required**, shows its subtext between the question text and the input, and can be used as a sub-question of a map question or of **Objects on the map**.

## Map questions

Map questions need a section with the map layout. The respondent draws on the map; each shape can carry sub-questions, which open in a popup on the placed feature and become attributes of that feature.

| Type | What the respondent does | Answer stored | Export |
|---|---|---|---|
| **Geo Point** (`point`) | Places a marker (on a phone, with the crosshair). | A point | A GeoJSON layer and a row in the observations table per marker |
| **Geo Line** (`line`) | Draws a route or line. | A line | A layer and a row per line; `lat`/`lon` are the centroid |
| **Geo Polygon** (`polygon`) | Outlines an area. | A polygon | A layer and a row per polygon; `lat`/`lon` are the centroid |
| **Spray area** (`spraycan`) | Sprays a cloud of dots with a brush — thicker where they are sure. One cloud per respondent; there is no "add another". | A multipoint (dots snapped to a 1 m grid, duplicates dropped) | A layer and a row per cloud with `dot_count` and `area_m2`; on a public results page, a density grid, never the dots |
| **Objects on the map** (`layer_objects`) | Taps objects from a reference layer the creator chose and answers the sub-questions about each one. Collects nothing itself. | One answer per object per sub-question | An `objects_<code>` sheet (one row per respondent per object) and a `<layer>.results.geojson` with per-object totals |

Settings that apply to map questions:

- **Min** and **Max** features (point, line, polygon): how many shapes one respondent may place. Empty = unlimited. The draw button shows "N of M marked" when a limit is set and disables at the maximum. The export stays one layer however many features a respondent adds.
- **Max dots per respondent** and **Brush size** (spray area): the brush is a screen size — **Small**, **Medium** or **Large** — so respondents zoom in to paint finer.
- Marker colour and icon (point, line, polygon, spray area) reach the respondent's map.
- **Objects on the map** replaces **Required** with a minimum number of objects to answer about (0 = optional), and shows its layer either as a browsable list or as a legend line (**Display as**).
- Sub-questions cannot themselves be map questions.

## Files

| Type | What the respondent does | Answer stored | Export |
|---|---|---|---|
| **Photo Upload** (`photo`) | Takes a photo with the phone camera or picks an image. | Up to **Max files (1–10)** image files | A cell naming each file's path inside the archive (`files/<session>/<code>__<name>`), paths separated by `; ` |
| **Audio Upload** (`audio`) | Records their voice in the browser, or uploads an audio file. | Audio files | As above |
| **Document Upload** (`document`) | Attaches a document (PDF, Office). | Document files | As above |

Files upload as soon as they are chosen, with progress, and the respondent can inspect and remove them before submitting. The platform cap is 25 MB per file; **Max file size, MB** can lower it per question. SVG and executables are refused. Files are private: they appear in the Responses table and in exports, never on a public results page. The GeoJSON + CSV export always includes them; the other formats include them only with **Include attached files** — see [Exports](/reference/exports/).

## Display blocks — collect nothing

| Type | What the respondent sees | Export |
|---|---|---|
| **Image** (`image`) | A picture chosen by the creator, with the subtext as its caption. | Nothing |
| **Formatted Text** (`html`) | The creator's formatted text — headings, bold, links. The subtext is the whole body. | Nothing |

For these two types the **Name** is an editor-only label; respondents never see it. Display blocks cannot be **Required**.

## Which types reach a public results page

Choice, multiple choice, rating, thumbs, number and range questions become chart blocks; point, line, polygon and spray area become map blocks; **Objects on the map** becomes an objects block. Text, single line text, ranking, date/time and file questions are never published — see [Share results publicly](/how-to/share-results-publicly/).

## Related

- [Exports](/reference/exports/)
- [Add a map question](/how-to/add-a-map-question/)
- [Add sub-questions](/how-to/add-sub-questions/)
- [Make a question conditional](/how-to/make-a-question-conditional/)
