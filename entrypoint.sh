#!/bin/sh

# If DATABASE_URL is set (Render), skip waiting for local db
if [ -z "$DATABASE_URL" ]; then
    echo "Waiting for postgres..."
    while ! pg_isready -h db -p 5432 -q; do
      sleep 0.1
    done
    echo "PostgreSQL started"
fi

# On Render these steps are handled by the deploy pipeline, not by container start:
# migrations and the superuser run as the web service's preDeployCommand (while the old
# instance is still serving), and static assets are collected into the image at build
# time. Doing them here would put them inside the deploy's 502 window — and would have the
# Celery worker and the acquisition cron migrate too, which they have no business doing.
#
# RENDER is set by Render on every service. Deliberately not reusing DATABASE_URL above:
# that answers "which database", not "which platform".
#
# Everywhere else — docker compose up, plain docker run — the start path is unchanged, so
# local development needs no extra step.
if [ -z "$RENDER" ]; then
    python manage.py migrate
    python manage.py collectstatic --no-input

    # Create superuser from env vars if set (DJANGO_SUPERUSER_USERNAME, DJANGO_SUPERUSER_EMAIL, DJANGO_SUPERUSER_PASSWORD)
    if [ -n "$DJANGO_SUPERUSER_USERNAME" ]; then
        python manage.py createsuperuser --noinput || true
    fi
fi

exec "$@"
