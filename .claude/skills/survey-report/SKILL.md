---
name: survey-report
description: Build an analysis report and a materials kit (archive) for a customer's survey, the way the Remington, Pszów and Whitehouse reports were done on 2026-10-01 — prod-DB facts, hotspots, maps (street + aerial per place), charts with their numbers, quotes, GeoJSON/CSV, an example report as HTML + PDF, README, ZIP. The "reporting module" prototype: we prepare the materials, the customer builds their own report from them. Use for "/survey-report <folder>", "сделай отчёт и архив по опросу", "подготовь материалы для отчёта", "как для Remington / Whitehouse".
license: MIT
metadata:
  author: mapsurvey
  version: "1.0"
arguments:
  - name: folder
    description: the customer's dossier folder under docs/marketing/user-outreach/ (e.g. the contact's handle)
    required: true
---

The deliverable is two things: **materials** the customer can reuse in their own report (every
chart as PNG + its numbers as CSV, maps, quotes, data for GIS) and **one example report** that
shows a way to put them together. The README says what is where. It goes out with the story
approval letter or on its own; the letter asks what is useful and what is missing, because the
answers shape the reporting module.

Worked examples (gitignored, on this machine):

| Survey | Generator | Kit |
|---|---|---|
| Remington (146 residents, 3 pin questions, long free text) | `docs/marketing/stories/remington-report.py` + `remington-analytics-variants.py` | `docs/marketing/stories/remington-archive/` (README is the model kit layout) |
| Pszów (164, points + lines + polygons, PL + EN) | `docs/marketing/stories/pszow-data/` — `build_data → maps_build → report → print_pdf → export_kit`, `i18n.py` for two languages | in that customer's dossier folder |
| Whitehouse (39, one pin + reasons, council paper) | `archive-<date>/` in the customer's dossier folder — `build_data.py, charts.py, places.py, report.py` | `<slug>-survey-archive.zip` in the same folder |

Copy the closest one into the new dossier and adapt; reuse `scripts/report_tools/` (maps, hotspots,
georeferencing, PDF).

## 1. Facts from the prod DB (read-only)

Same filter as the `customer-story` skill: canonical survey + every version
(`id = X OR canonical_survey_id = X`), sessions not deleted, `opened_by_kind='external'`,
`validation_status NOT IN ('not_approved','on_hold')`, at least one answer. Sum by question
`code`, never by id. Columns that bite: `survey_answer.point` / `line` / `polygon` /
`selected_choices` (jsonb) / `text` / `numeric`; `survey_question.parent_question_id_id`;
`survey_surveysection.survey_header_id`; layers in `survey_surveymaplayer.geojson_gz`
(`encode(...,'base64')`, gzip). One row per session (started, duration =
`last_activity_at - start_datetime`, device and referrer from the `session_start` event metadata,
pin, sub-answers) is the table everything else is built from. Opens vs answered by day and by
version tells you how the launch went (a republish an hour after launch usually means
residents struggled with something).

Export the survey structure (`export_survey <uuid> --mode structure` with prod `SQL_*`) for
labels and screenshots; never open the live survey.

## 2. Analysis

- **Who answered**: choice questions as horizontal bars with n and %; say "several options
  allowed" when it is a multichoice. Do not chart race, language or income.
- **How it ran**: opens vs completed per day, arrival (Facebook / website / direct) and device,
  time of day. Opens include link previews; say so.
- **Where**: hotspots (`geo.hotspots`, 120 m cells, merge 150 m, ≥2 pins), each named by street
  from the map (Nominatim gives road names; check them by eye), with count, reasons and the
  quotes near it. Distance to the nearest existing feature (`geo.nearest`) when the survey had a
  reference layer — it turns "too far from an existing one" into a number.
- **Why / in their words**: reasons as bars; free text by keyword themes (one answer can count
  under several), word clouds only as an extra; quotes verbatim, short, anonymous, never naming
  people, developers or addresses.
- **Against the customer's own decision** if they have one (a council paper): match by
  street, and when they gave a map, georeference it on shared features (`geo.georeference`)
  instead of guessing.

## 3. Maps

`maplib.render` specs: overview with numbered hotspots + list, heat map per question (marks as
heat in anything public; points are fine in the customer's kit), per hotspot a street map AND an
aerial view with the pins (and the reference layer) drawn on, the existing + recommended layer
when there is one. An interactive single-file Leaflet map (data inline, popups built with
textContent so a resident's note is never parsed as HTML) with one toggle per layer.

## 4. Charts

PNG for pasting, SVG where editable matters, a CSV with the same file name for every chart.
Palette from the `dataviz` skill (categorical blue/orange/teal; one hue per question across
maps and charts). Integer axes for counts. Every chart has a one-line source note.

## 5. Example report

Self-contained HTML (pictures embedded), sections in this order: headline numbers · how the
survey ran · who answered · where (hotspots + heat) · the places up close · why · in their words
· against the decision (if any) · what stands out (5 numbered takeaways, each tied to a number)
· about this report (filter, grouping, anonymity, sources, "the data belongs to <customer>").
Then `scripts/report_tools/pdf.py`: an A4 PDF for print and a `--single` one-page PDF for screens.

## 6. Kit and README

```
README.txt  report.html  report.pdf
maps/       interactive-map.html, overview, heat, hotspots(+list), existing+recommended
places/     hotspot-N-map.png, hotspot-N-satellite.jpg
charts/     <nn>-<slug>.png (+ .svg)
data/       <nn>-<slug>.csv per chart, suggested/answers .geojson + .csv, hotspots .geojson + .csv,
            responses.csv (one row per response, anonymous ids R001…), the customer's layers
quotes/     quote candidates, quotes by place (when there is enough free text)
```
README: what each folder holds, the method in one paragraph, attributions (© OpenStreetMap
contributors; aerial © Maxar / Mapbox), "the data belongs to <customer>". Zip it into the
dossier as `<slug>-survey-archive.zip` (≈15 MB is fine for email).

## 7. Hand-off

In the Remington-style letter (see `customer-story` §4): a "Separately: I am building a reporting
module for Mapsurvey…" paragraph, what the kit holds in one sentence, "I would love to know what
is useful in it and what is missing." Record the reply in the dossier and in the reporting-module
notes; Stack item waits on it.

## Rules

- Resident data never enters the repo (it is public). Generators and outputs stay in the
  gitignored dossier; only generic code goes to `scripts/report_tools/`.
- No individual answer is identifiable: anonymous ids, no free text that names people or homes.
- Every number in the report carries its date and filter in the dossier notes; the kit is
  rebuilt when the survey closes.
