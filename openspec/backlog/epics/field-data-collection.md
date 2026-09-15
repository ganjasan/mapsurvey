# Field Data Collection

**Slug**: field-data-collection
**Created**: 2026-08-23
**Tier (2026-08-23)**: **Pro** for the collection-scale features (volunteer identity, QA,
offline, attachments); the plain browser-based flow stays Free — a volunteer must never hit
a paywall, and the buyer is the organisation running the campaign, not the person walking
the route.

## Description

Turning Mapsurvey from "respondents give opinions on a map" into "a crew collects
observations on a map". Two audiences, one pipeline:

- **Volunteers / citizen scientists** — untrained people with their own phones, no app, no
  account, walking an assigned area and recording what they see. This is the wedge: no
  competitor serves them without an app install or per-user licensing.
- **Field professionals** — ecologists, archaeologists, surveyors, asset inspectors who
  need offline, attachments, GPS quality and record-level QA. This is where the money and
  the engineering are.

**Positioning note.** The project's stated line was "participatory geo-surveys, NOT field
GIS collection" ([[project-positioning]]). As of 2026-08-23 that line moves: field
collection is in scope. What does **not** change is who we optimise for — the untrained
person with a browser. We enter the field market from the volunteer end, where Fulcrum,
Survey123 and QField are weakest, rather than competing on GIS depth.

## Origin

Inbound from the City of Olney, IL (2026-08-21): 105 volunteers, 35 paper-map zones, an
annual wildlife count running since 1977 ([[lead-olney-squirrel-count]]). Everything in
their workflow mapped onto existing features except zone overlays and resume — which is
exactly the shape of the gap. Second signal: Brevard NC's twin count is being revived
after lapsing. Third: r/gis field-collection feedback (2026-04-07,
[[features-from-field-gis-feedback]]) where offline was the unanimous top requirement.

## Scope

### Tier 1 — Volunteer collection (browser, online)
Ships value without the offline investment; sells to Olney-class campaigns in weeks.

- FD-1: Reference overlay layers — creator uploads GeoJSON (zones, boundaries), respondents see it
- FD-2: Volunteer links — per-person tokenised links that tag sessions and preset the assigned area
- FD-3: Resume — a volunteer reopening their link sees the features they already placed
- FD-4: Photo attachment inside the observation popup
- FD-5: "Place at my location" — GPS button as an alternative to tapping the map
- FD-6: Campaign recurrence — re-run the same survey next season and compare years
- FD-14: Answer-driven map context — picking your area zooms the map to it and hides the rest
- FD-15: Survey welcome page — a real first screen instead of a Formatted Text block faking one
- FD-16: Map-less sections — classic full-width form layout for the non-map parts of a survey
- FD-17: Draw an overlay layer in the editor instead of uploading (#148, split from FD-1 2026-08-25)

### Tier 2 — Field GIS (offline and QA)
Bigger engineering; each item is a prerequisite for selling to professional crews.

- FD-7: Offline architecture ADR — decide PWA-over-existing vs a schema-driven field client
- FD-8: Offline collection + sync queue (depends on FD-7)
- FD-9: GPS metadata (accuracy, timestamp, optional averaging) stored as feature properties
- FD-10: Record-level QA — approve/reject individual features, not just whole sessions
- FD-11: Media to S3 — prerequisite for attachments at field volume ([[project-deploy-downtime-disk]])
- FD-12: Editable datasets — revisit and update an existing feature across sessions
- FD-13: Shapefile / GeoPackage export (existing item #8)

## Non-goals

- Native mobile apps. The browser is the wedge, not a limitation to fix.
- Sub-metre survey-grade workflows (external GNSS beyond what the OS exposes, RTK).
- Becoming a GIS. Analysis stays where our users already do it — QGIS, ArcGIS, a spreadsheet.

## Open questions

- Does Tier 1 alone close an Olney-class deal at $49/mo? Olney is the live test.
- Is offline (FD-7/FD-8) worth its cost before a paying field customer asks by name?
