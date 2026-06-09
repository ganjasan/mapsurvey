# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

```bash
# Docker (recommended)
docker-compose up --build              # Start all services
docker-compose up db                   # Start only PostgreSQL/PostGIS

# Local development (venv in ./env)
source env/bin/activate                # Activate virtual environment
pip install -r requirements.txt        # Install dependencies (or use pipenv)
python manage.py migrate               # Apply database migrations
python manage.py runserver             # Start development server (port 8000)
python manage.py createsuperuser       # Create admin user
python manage.py collectstatic         # Collect static files

# Testing (requires running PostGIS on port 5434)
./run_tests.sh survey                  # Run all survey app tests
./run_tests.sh survey -v2              # Verbose output
./run_tests.sh survey.tests.SmokeTest  # Run specific test class
```

## Parallel worktrees (port isolation)

`run_dev.sh`, `run_tests.sh`, and `run_e2e.sh` derive every host port from a single
`PORT_OFFSET` so multiple worktrees can run dev + tests at the same time without
colliding. To set up a worktree: `cp .env.ports.example .env.ports` and pick a unique
offset (keep the registry in that file current). Ports = base + offset
(PostGIS `5434`, Redis `6379`, web `8000`). `COMPOSE_PROJECT_NAME` isolates the docker
stack per worktree. Offset `0` reproduces the original ports. `.env.ports` is gitignored.

## Testing

Tests use Django's built-in test framework with PostGIS. Django automatically creates a separate `test_mapsurvey` database.

**Prerequisites**: PostGIS container must be running (`docker compose up -d db`)

**Test location**: `survey/tests.py`

**Writing tests**: Use `django.test.TestCase` and GIVEN/WHEN/THEN pattern for docstrings.

**Redis**: a few tests (`LastActivityMiddlewareTest`) exercise cache-gated code and need
Redis on `localhost:6379`. `run_tests.sh` does not start it; without it those tests fail
with `UserActivity.DoesNotExist`.

## Load testing

`loadtest/lecture-burst.js` (k6) reproduces a lecture-hall burst — N students opening the
same map survey at once. It does **not** reproduce locally (a dev machine is far faster
than a 0.5 CPU Render Starter instance), so run it against a Render PR preview, never
production. Seed the preview's empty database first with
`python manage.py seed_loadtest_survey`. See `loadtest/README.md`.

## Architecture Overview

This is a Django-based geospatial survey platform using PostGIS for storing geographic data (points, lines, polygons).

### Project Structure

- `mapsurvey/` - Django project settings and root URL configuration
- `survey/` - Main application with all business logic

### Core Data Model Hierarchy

```
Organization
└── SurveyHeader (survey definition)
    ├── SurveySection (logical groupings with map position)
    │   ├── Question (supports 12+ input types including GIS)
    │   └── OptionGroup → OptionChoice (reusable choice sets)
    └── SurveySession (user's survey attempt)
        └── Answer (stores responses with GIS geometry fields)
```

### Key Patterns

**Dynamic Form Generation**: `SurveySectionAnswerForm` in `survey/forms.py` dynamically builds form fields based on question `input_type`. Each type maps to specific Django fields and custom Leaflet widgets for GIS input.

**Question Types**: `text`, `text_line`, `number`, `choice`, `multichoice`, `range`, `rating`, `datetime`, `point`, `line`, `polygon`, `image`, `html`

**Hierarchical Questions/Answers**: Both Question and Answer models support self-referential parent relationships via `parent_question_id` and `parent_answer_id` for conditional sub-questions.

**Session Management**: Survey sessions are created on first section view and tracked via `request.session['survey_session_id']`.

**Data Export** (`download_data` view): Exports survey responses as ZIP containing:
- GeoJSON files for each geo-question (point/line/polygon)
- CSV file for non-geographic data

**Public results page**: Creators expose aggregated results at `/r/<slug>/` via `PublicResultsPage` (1:1 with `SurveyHeader`) + ordered `PublicResultsBlock`s. Config tab at `/editor/surveys/<uuid>/public-results/`. Rendering logic in `survey/public_results.py` (`PublicResultsService`, `render_page_data`, `freeze_page`/`unfreeze_page`); editor views in `survey/public_results_editor.py`. Aggregates run over CLEAN sessions only (not deleted, excludes `not_approved`/`on_hold`) across the canonical survey + all versions. Privacy: k-anonymity masks buckets `<K` (default 3); geo popups expose only creator-selected `geo_label_fields`; individual free-text answers are never published. Hybrid `live` (60s cache) vs `frozen` (snapshot) mode. Visibility `public` (indexed, in sitemap) vs `unlisted` (noindex). The page config is intentionally NOT included in survey ZIP export/import.

**Registration abuse prevention**: `/accounts/register/` is served by `AbuseProtectedRegistrationView` (subclass of `AsyncEmailRegistrationView`). Three layered defenses run in order: honeypot field `website` (silent fake-success redirect), per-IP rate limit (`django-ratelimit`, fail-open on Redis outage), Cloudflare Turnstile siteverify (fail-closed on network error, dev-bypass when `TURNSTILE_SECRET_KEY=""`). Helpers in `survey/abuse.py`. Audit log in `AbuseEvent` model. Real client IP via `survey.middleware.CloudflareIPMiddleware` reading `CF-Connecting-IP` only when `CLOUDFLARE_TRUSTED=True`.

**Acquisition metrics (top of the funnel)**: the staff funnel dashboard at
`/admin/survey/funnelreport/` shows Google impressions → landing visits → registrations → demo
opens above the registration-onward stages. External numbers are never fetched during a request:
`python manage.py sync_acquisition_metrics [--days N] [--source gsc|plausible]` pulls Search Console
and Plausible into `AcquisitionDaily` (keyed by source/date/segment, re-runnable — a rerun overwrites
the window, which is how GSC's retroactive revisions land). Run daily by the
`mapsurvey-acquisition-sync` cron service; the provider keys live only on that service. Clients in
`survey/acquisition.py`, dashboard aggregation in `survey/funnel.py` (`AcquisitionService`).
Per-source state in `AcquisitionSyncState` surfaces "not configured" / "failing" / stale on the
dashboard itself, so a stalled sync is visible where the numbers are read. GSC's "marketing pages"
segment is defined by *excluding* `ACQUISITION_NON_MARKETING_PREFIXES` (`/surveys/` above all — those
impressions are customers' respondents finding their own survey). **GSC aggregation gotcha**: Search
Console counts impressions property-level when no page filter is present and page-level when one is,
and the totals differ (1329 vs 1717 over the same 14 days). Both segments therefore query *with* a
page filter — the whole-property one uses a match-everything expression solely to stay in page-level
mode. Never drop that filter: mixing modes makes the marketing segment exceed the whole property. Our
stored whole-property number reads higher than the GSC UI's total for the same window, by design. Demo opens: total from
`SurveySession` on the `DEMO_SURVEY_URL` survey (retroactive), anonymous/signed-in split from
`DemoOpen` (forward-only; the user FK lives there and never on `SurveySession`, which must not link
customers' respondents to platform accounts).

### URL Structure

- `/` - Redirects to login or editor
- `/editor/` - Dashboard for authenticated users
- `/surveys/` - Public survey list
- `/surveys/<name>/` - Survey entry (redirects to first section)
- `/surveys/<name>/<section>/` - Survey section form
- `/surveys/<name>/download` - Export data as ZIP
- `/r/<slug>/` - Public survey results page (aggregated, read-only)
- `/admin/` - Django admin (surveys configured entirely here)

### Environment Variables

Required in `.env`:
- `SECRET_KEY`, `DEBUG`, `DJANGO_ALLOWED_HOSTS`
- Database: `SQL_ENGINE`, `SQL_DATABASE`, `SQL_USER`, `SQL_PASSWORD`, `SQL_HOST`, `SQL_PORT`
- Optional S3: `USE_S3=TRUE`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_STORAGE_BUCKET_NAME`
- Acquisition metrics (optional; unset = "not configured" on the dashboard, never a zero):
  `GSC_SITE`, `GSC_SERVICE_ACCOUNT_JSON` (key contents; production) or `GSC_KEY` (key file path;
  local dev), `PLAUSIBLE_API_KEY`, `PLAUSIBLE_SITE_ID`. See `.env.example`. **This repo is public**
  — no key path is defaulted in `settings.py`; keep the path in your gitignored `.env`

### GeoDjango Notes

- Database engine must be `django.contrib.gis.db.backends.postgis`
- Models use `PointField`, `LineStringField`, `PolygonField` from `django.contrib.gis.db.models`
- Admin uses `LeafletGeoAdmin` for map-based editing
- Custom Leaflet draw widgets in `survey/forms.py` for frontend geometry input

## Workflow: Spec Driven Development (OpenSpec)

This project uses **Spec Driven Development** via the `openspec` CLI. All changes go through the artifact pipeline:

```
/opsx:new → /opsx:ff or /opsx:continue → /opsx:apply → /opsx:archive
```

**Key rule**: When asked to make changes or fix bugs, **always work through OpenSpec first**:
- If there is an active change related to the request — update its specs/design/tasks before editing code
- If no relevant change exists — create a new one (`/opsx:new`) before implementing

Never jump straight to code without a corresponding change in `openspec/changes/`.

## Project Management

**Task list**: See `TODO.md` for planned features and tasks
