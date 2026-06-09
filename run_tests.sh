#!/bin/bash
# Run Django tests with PostGIS database

# Per-worktree port isolation (see .env.ports.example). Tests reuse the dev
# PostGIS container of this worktree; Django creates its own test_ database.
[ -f .env.ports ] && source .env.ports
PORT_OFFSET="${PORT_OFFSET:-0}"
export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-mapsurvey}"
export HOST_DB_PORT=$((5434 + PORT_OFFSET))

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
SQL_PORT=$HOST_DB_PORT \
python manage.py test "$@"
