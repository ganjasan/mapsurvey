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

## Testing

Tests use Django's built-in test framework with PostGIS. Django automatically creates a separate `test_mapsurvey` database.

**Prerequisites**: PostGIS container must be running (`docker compose up -d db`)

**Test location**: `survey/tests.py`

**Writing tests**: Use `django.test.TestCase` and GIVEN/WHEN/THEN pattern for docstrings.

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

### URL Structure

- `/` - Redirects to login or editor
- `/editor/` - Dashboard for authenticated users
- `/surveys/` - Public survey list
- `/surveys/<name>/` - Survey entry (redirects to first section)
- `/surveys/<name>/<section>/` - Survey section form
- `/surveys/<name>/download` - Export data as ZIP
- `/admin/` - Django admin (surveys configured entirely here)

### Environment Variables

Required in `.env`:
- `SECRET_KEY`, `DEBUG`, `DJANGO_ALLOWED_HOSTS`
- Database: `SQL_ENGINE`, `SQL_DATABASE`, `SQL_USER`, `SQL_PASSWORD`, `SQL_HOST`, `SQL_PORT`
- Optional S3: `USE_S3=TRUE`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_STORAGE_BUCKET_NAME`

### GeoDjango Notes

- Database engine must be `django.contrib.gis.db.backends.postgis`
- Models use `PointField`, `LineStringField`, `PolygonField` from `django.contrib.gis.db.models`
- Admin uses `LeafletGeoAdmin` for map-based editing
- Custom Leaflet draw widgets in `survey/forms.py` for frontend geometry input

## Project Management

**Task list**: See `TODO.md` for planned features and tasks
