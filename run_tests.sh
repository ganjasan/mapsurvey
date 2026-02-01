#!/bin/bash
# Run Django tests with PostGIS database

# Ensure db container is running
docker compose up -d db

# Wait for database to be ready
sleep 2

# Run tests with proper environment
source env/bin/activate
SQL_ENGINE=django.contrib.gis.db.backends.postgis \
SQL_DATABASE=mapsurvey \
SQL_USER=mapsurvey \
SQL_PASSWORD=mapsurvey \
SQL_HOST=localhost \
SQL_PORT=5434 \
python manage.py test "$@"
