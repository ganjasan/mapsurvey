#!/bin/sh

# If DATABASE_URL is set (Render), skip waiting for local db
if [ -z "$DATABASE_URL" ]; then
    echo "Waiting for postgres..."
    while ! pg_isready -h db -p 5432 -q; do
      sleep 0.1
    done
    echo "PostgreSQL started"
fi

python manage.py migrate
python manage.py collectstatic --no-input --clear

# Create superuser from env vars if set (DJANGO_SUPERUSER_USERNAME, DJANGO_SUPERUSER_EMAIL, DJANGO_SUPERUSER_PASSWORD)
if [ -n "$DJANGO_SUPERUSER_USERNAME" ]; then
    python manage.py createsuperuser --noinput || true
fi

exec "$@"
