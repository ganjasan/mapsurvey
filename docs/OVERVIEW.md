# Mapsurvey — functional overview

## What it is

Mapsurvey is an open-source platform (AGPLv3) for **participatory mapping surveys**: online
questionnaires in which people answer by drawing on a map as well as by ticking boxes. A town
asks "where is it unsafe to cross?", "draw the route you walk to school", "mark where a new
bench should go", and residents answer with points, lines and polygons. The result is spatial
data a planner can use directly in GIS.

It works for any organisation that needs to know *where* people experience something, with
or without a GIS department. Groups already using it: municipalities and public agencies,
community and neighbourhood councils, universities and students, planning and design
consultancies, NGOs, citizen-science projects and educators. It runs as a hosted service at mapsurvey.org (free tier
with unlimited surveys and responses) or on the organisation's own server via Docker.

## Who uses it, for what

| Role | Uses Mapsurvey to |
|---|---|
| Municipality / public agency | Run a public consultation on a plan, a street, a park; collect locations of problems and ideas |
| Community / neighbourhood council | Ask residents where something should go (bins, benches, crossings) or what a neighbourhood plan should cover |
| Planning / design consultancy | Run engagement for a client project and hand over GIS-ready results |
| University researcher or student | Run PPGIS (public-participation GIS) studies, campus surveys, theses; export to QGIS / R / Python |
| NGO / citizen-science project | Map community needs, observations or counts with volunteers |
| Educator | Let students map their neighbourhood or campus as a geography or civics exercise |
| Respondent | Answer on a phone or computer, no account, no app to install |

## Main functions

**Building a survey (creator, signed in)**
- Visual editor: sections, questions, drag-and-drop ordering, live preview.
- Question types: short and long text, number, single and multiple choice (with "other"),
  rating, ranking, range, date/time, thumbs up/down, **point, line, polygon, spray area**,
  objects-on-the-map with reactions, photo, audio and document upload, plus image and
  formatted-text display blocks.
- Each section has its own map view (centre, zoom, basemap); reference layers (GeoJSON) can be
  shown to respondents for context; place search.
- Conditional questions and sections; multi-language surveys (every text translatable).
- Optional AI drafting of a first version from a typed brief (can be disabled; never sees responses).
- Workspaces with members and roles; comment threads on questions, sections and responses.

**Answering (respondent, anonymous)**
- Open link, no login. Mobile-first map input with crosshair placement and finish buttons.
- Progress indicator and back navigation that keeps answers.
- Optional shared map: see others' marks and agree with them instead of duplicating.

**Results**
- Responses table and map, per-question analytics, response drawer per session, tags and notes.
- **Export**: one ZIP with GeoJSON (geometry answers) and CSV (all answers), any time.
- **Public results page**: creator-curated charts and anonymous map features at a short URL;
  no individual text answers; small groups masked by default (k-anonymity, K=3, adjustable by the creator).
- Survey structure import/export as JSON, so a survey can move between installations.

**Safety**
- Phishing screening and holds at publication, "Report this survey" on every survey page,
  staff review, registration abuse defences. See the Acceptable use & safety policy.

## Architecture

```
Browser (HTMX + Leaflet, no SPA)
   │
Django 4.2 + GeoDjango ── Celery workers (email, screening notices, purge jobs)
   │                          │
PostgreSQL + PostGIS        Redis (broker / cache)
   │
Object storage (local disk or any S3-compatible store) for uploads
```

- Single Django project, app `survey`. Data model: Organization → SurveyHeader → SurveySection
  → Question; SurveySession → Answer (text, numeric, geometry, choices, files).
- Basemaps: any XYZ tile service, set by `MAPBOX_URL` / `MAPBOX_ACCESS_TOKEN` (Mapbox by default
  on mapsurvey.org).
- All external services are optional and switched by environment variables:

  | Service | Purpose | Variables (empty = off / local default) |
  |---|---|---|
  | Mapbox (or any XYZ tiles) | Basemaps | `MAPBOX_URL`, `MAPBOX_OUTDOORS_URL`, `MAPBOX_ACCESS_TOKEN` |
  | PostHog | Product analytics on creator pages only | `POSTHOG_PROJECT_KEY`, `POSTHOG_API_HOST` |
  | AI provider (Anthropic or Google Gemini) | Optional AI drafting of a survey | `AI_PROVIDER`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY` |
  | S3-compatible storage | Uploads | `USE_S3`, `AWS_*` (local disk when unset) |
  | SMTP | Account email | `EMAIL_BACKEND` and Django email settings (console by default) |

## Run it yourself

```bash
git clone https://github.com/ganjasan/mapsurvey.git
cd mapsurvey
cp .env.example .env      # set SECRET_KEY, DJANGO_ALLOWED_HOSTS, database
docker compose up --build # http://localhost:8000
```

Configuration reference: README → Configuration. Tests: `./run_tests.sh survey`.
Management commands: `export_survey`, `import_survey`.

## Data and standards

- Geometry: GeoJSON (RFC 7946), WGS 84 (EPSG:4326). Tabular: CSV (UTF-8).
- Interfaces in 11 languages (en, de, fr, es, pt, pl, id, nl, it, et, fi); survey content in any language.
- Privacy and data handling: https://mapsurvey.org/trust/
- Help centre (tutorial, how-to guides, reference, troubleshooting, FAQ, and essays on participatory mapping): https://help.mapsurvey.org/

## Project

Owner: Artem Koniukhov (Kyrgyz Republic). Licence: AGPLv3. Security reports: SECURITY.md.
Contributing: CONTRIBUTING.md. Code of conduct: CODE_OF_CONDUCT.md. Terms and acceptable use: https://mapsurvey.org/terms/
