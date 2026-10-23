---
title: Use the REST API
description: Build, publish and read surveys from a script, a GIS pipeline or your own tool — your first calls with curl and Python, how live surveys and errors work, and a QGIS note.
sidebar:
  order: 15
---

The REST API does over HTTP what you do in the editor: create a survey, add sections and
questions, publish it, and read or export its responses. Use it from a script, a reporting
pipeline, a QGIS workflow or your own app.

**The API is a Pro feature.** Calls on a survey need the workspace that owns it to be on Pro;
anywhere else they answer `pro_required`. See [Plans and billing](/reference/plans-and-billing/).
Every endpoint and field is listed in the [REST API reference](/reference/api/).

## Before you start

1. [Create a personal access token](/how-to/personal-tokens/) for the **REST API**. Leave
   **publish** and **delete** off unless your tool must do those.
2. Keep the token in an environment variable, not in your code:

```bash
export MAPSURVEY_TOKEN=msk_…
```

## Your first calls

Check what the token reaches — your workspaces, their plans and whether the API is available:

```bash
curl -H "Authorization: Bearer $MAPSURVEY_TOKEN" https://mapsurvey.org/api/v1/me
```

Create a survey, add a question to its first section and publish it:

```bash
API=https://mapsurvey.org/api/v1
AUTH="Authorization: Bearer $MAPSURVEY_TOKEN"

# 1. A new survey (name the workspace by its slug if you belong to several)
curl -s -X POST $API/surveys -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"name": "Park improvements", "workspace": "my-team"}'
# → {"uuid": "…", "sections": [123], "status": "draft", …}

# 2. A point question in section 123
curl -s -X POST $API/surveys/<uuid>/sections/123/questions -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"name": "Where would you add a bench?", "input_type": "point", "required": true}'

# 3. Publish (needs the surveys:publish permission)
curl -s -X POST $API/surveys/<uuid>/publish -H "$AUTH" -H "Content-Type: application/json" -d '{}'
# → {"status": "published", "review": null, "url": "https://mapsurvey.org/surveys/<uuid>/"}
```

The same in Python, reading responses page by page:

```python
import os, requests

API = "https://mapsurvey.org/api/v1"
session = requests.Session()
session.headers["Authorization"] = f"Bearer {os.environ['MAPSURVEY_TOKEN']}"

def responses(survey_uuid):
    cursor = None
    while True:
        page = session.get(f"{API}/surveys/{survey_uuid}/responses",
                           params={"limit": 200, "cursor": cursor}).json()
        yield from page["items"]
        cursor = page["next_cursor"]
        if not cursor:
            break

for r in responses("<uuid>"):
    print(r["number"], [a["question"] for a in r["answers"]])
```

## Editing a live survey

A published survey takes **wording** changes in place — question names, help text, translations,
new options — exactly as in the editor. A change of **structure** — adding, deleting or
reordering sections and questions, changing a question's type, removing an option people have
already chosen, a visibility rule — is refused with `409 draft_required`, because it would change
the survey under people who are answering it.

Make those changes on unpublished changes, then publish them:

```bash
curl -s -X POST $API/surveys/<uuid>/draft -H "$AUTH"           # → {"uuid": "<draft uuid>", …}
# … edit <draft uuid> like any draft survey …
curl -s -X POST $API/surveys/<uuid>/draft/publish -H "$AUTH" -H "Content-Type: application/json" -d '{}'
```

Respondents keep the live survey until you publish. See
[Edit a published survey](/how-to/edit-a-published-survey/) for what counts as structure.

## Errors

Every error is `{"error": "<code>", "detail": "<text>"}`. Branch on `error`, never on `detail`.
The ones you will meet first:

- `pro_required` — the survey's workspace is not on Pro; `upgrade_url` is its billing page.
- `scope_missing` — the token lacks a permission; create one that has it.
- `validation` — `fields` says which field is wrong and why. A field the API does not know is
  refused by name, so a typo never passes silently.
- `answers_at_risk` — a delete would remove answers; repeat it with `acknowledge_answer_loss=true`
  once you mean it.
- `rate_limited` — wait the `Retry-After` seconds.

The full list is in the [reference](/reference/api/#errors).

## Exporting data

`GET /surveys/<uuid>/export?format=gpkg` returns the same file as **Export data** on the
Responses page: `zip` (GeoJSON + CSV), `xlsx`, `csv`, `gpkg`, `shp` or `kml`; add `files=true`
for uploaded photos and documents. See [Export responses](/how-to/export-responses/) for what each
format contains.

## A note for QGIS

The quickest route into QGIS is the GeoPackage export: download
`/surveys/<uuid>/export?format=gpkg` with your token (a Python console snippet, or **Layer → Add
Layer → Add Vector Layer** after downloading) and open it — one layer per map question, with the
sub-question answers as attributes. Reference layers come from
`/surveys/<uuid>/layers/<id>/geojson`.

## Limits

600 reads and 60 writes a minute per token, 5 000 calls a day, and daily caps on creating (50)
and deleting (20) surveys, importing (20) and exporting (100). The API sends no cookies and answers
any origin, so a browser app can call it directly — keep the token out of public pages.
