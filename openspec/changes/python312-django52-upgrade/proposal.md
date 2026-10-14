# Proposal: python312-django52-upgrade

## Why

Production runs Python 3.9.25 and Django 4.2.27. Python 3.9 left upstream security
support on 2025-10-05; Django 4.2 LTS left extended support in April 2026. Since then
neither receives security fixes. The cause is quiet: `Pipfile` says `django = "*"` under
`python_version = "3.9"`, and Django 5.0+ needs Python 3.10, so every `pipenv lock`
re-pins 4.2 without anyone choosing it. Side effects already visible: `posthog` is pinned
to 6.9 because 7.x needs 3.10; the repository tracks bytecode for CPython 3.7 and 3.9;
`django.utils.timezone`/`USE_L10N` leftovers sit in settings.

## What changes

- **Runtime**: `python:3.12-slim` (security support to October 2028) and **Django 5.2 LTS**
  (support to April 2028), pinned as `django = "~=5.2"` with `python_version = "3.12"`,
  `Pipfile.lock` regenerated under 3.12. The web service, the Celery worker and the cron
  share the image, so one Dockerfile line moves all three.
- **Code**: the known incompatibilities — `USE_L10N` (removed in 5.0), `CheckConstraint(check=)`
  (`condition=` since 5.1, `check` gone in 6.0), `datetime.utcnow()` (deprecated in 3.12),
  the tracked `.pyc` files — plus whatever the suite reveals under 5.2 with
  `RemovedInDjango60Warning` treated as an error.
- **Respondent form markup stays identical**: Django 5.0 renders `{{ form }}` with
  `div.html` instead of `table.html`; two respondent templates render the whole form that
  way, and the section page's CSS and JS were written against the table structure. A
  project form renderer keeps `table.html` for this change; moving to div markup is its own
  change with its own mockup review.
- **Third-party packages** are re-resolved and checked against Django 5.2 support:
  django-registration, django-leaflet, django-ratelimit, django-storages, django-redis,
  django-debug-toolbar, celery, pandas/numpy, Pillow, psycopg2-binary. `posthog` is unpinned
  to 7.x behind the `PostHogErrorTrackingTest` canaries.
- **Developer environment**: the shared `env` venv is Python 3.9 and every worktree symlinks
  it; the upgrade creates a 3.12 venv and documents the switch (CLAUDE.md, worktree
  bootstrap).

## Out of scope

psycopg 3 (Django 5.2 works with psycopg2-binary; the driver swap is a separate decision),
Django 6.0, async views or ORM, div-based form markup, any other dependency major bumps
the resolver does not force.

## Impact

- Files: `Dockerfile`, `Pipfile`, `Pipfile.lock`, `mapsurvey/settings.py`, `survey/models.py`
  (+ a migration if the autodetector wants the constraint re-stated), `survey/serialization.py`,
  tests, `CLAUDE.md`, `.env.ports.example`; six tracked `.pyc` files removed.
- Specs: `render-deployment` (ADDED requirement "Runtime versions are supported upstream").
- Rollout through a PR preview: full suite, the Playwright respondent flow (`run_e2e.sh`),
  `scripts/gunicorn_recycle_check.py`, and the k6 lecture-burst harness against the preview
  to compare latency and memory with the current numbers before merge.
- No kill switch (owner rule); the previous image is the rollback, which Render keeps.
