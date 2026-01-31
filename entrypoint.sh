#!/bin/sh

# If DATABASE_URL is set (Render), skip waiting for local db
if [ -z "$DATABASE_URL" ]; then
    echo "Waiting for postgres..."
    while ! nc -z db 5432; do
      sleep 0.1
    done
    echo "PostgreSQL started"
fi

python manage.py migrate
python manage.py collectstatic --no-input --clear

exec "$@"
