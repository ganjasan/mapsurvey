---
title: Import of “…” failed
description: A ZIP survey archive uploaded on the dashboard ended as a red card with an error instead of a new survey.
sidebar:
  order: 30
---

You uploaded a ZIP archive through **Import** on the dashboard, the card said **Importing “…”** for a while, then turned red: **Import of “…” failed:** followed by a reason.

## Why it happens

An import runs in the background and reads the archive the way Mapsurvey's own backup export writes it: `survey.json` for the structure, `responses.json` for the data, a `layers/` folder for reference layers. The reason after the colon says which check failed.

- **Invalid ZIP archive** — not a ZIP, or a download that was cut short.
- **Archive must contain survey.json and/or responses.json** — a ZIP of something else, such as a GeoJSON layer or an analysis export. Only a backup is importable.
- **Unsupported format version** — the archive comes from a different version of Mapsurvey.
- **Missing 'survey' field**, **Invalid input_type**, **requires choices**, **Invalid WKT**, or **The archive could not be read: …** — the archive was edited by hand or generated elsewhere, and a field is missing or has the wrong shape.
- **Data-only import requires existing survey '…'** or **Multiple surveys found with name '…'** — a **Data Only** backup needs exactly one survey with that name in your workspace to receive the responses.
- **The import failed unexpectedly. The error has been reported.** — a problem on our side, already logged.

A green card with a list underneath is a success with warnings: a password is never carried over, and layers beyond the tenth or ones that fail validation are skipped.

## What to do

1. Check what you uploaded. The importable file comes from **More actions › Export data › Backup (survey file)**, as **Structure Only**, **Data Only** or **Full Backup**.
2. If the error names a field, undo any hand edit, or export the survey again from the installation it came from.
3. For a **Data Only** archive, import the matching **Structure Only** backup first, make sure the survey name is unique in the workspace, then import the data.
4. Upload the archive again with **Import › Select ZIP archive**.
5. Dismiss the failed card with the cross; it also disappears after a day.

## If it keeps happening

[Contact support](https://mapsurvey.org/?support=1) with the full text of the red card and the archive itself, or its size and where it was exported. If the message says the error has been reported, tell us the time of the attempt.
