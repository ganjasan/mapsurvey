#!/bin/bash
# Run Django tests with PostGIS and Redis

# Per-worktree port isolation (see .env.ports.example). Tests reuse the dev
# PostGIS and Redis containers of this worktree; Django creates its own test_
# database.
[ -f .env.ports ] && source .env.ports
PORT_OFFSET="${PORT_OFFSET:-0}"
export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-mapsurvey}"
export HOST_DB_PORT=$((5434 + PORT_OFFSET))
export HOST_REDIS_PORT=$((6379 + PORT_OFFSET))

# Redis matters even though few tests touch it directly. settings.py falls back
# to redis://localhost:6379/1 when REDIS_URL is unset, and on a machine running
# several projects that port belongs to whichever one started first — so the
# suite would connect to a stranger's Redis and write into its database.
# CACHES sets IGNORE_EXCEPTIONS, so this fails silently rather than loudly:
# cache-backed behaviour (LastActivityMiddleware's throttle, rate limiting) just
# quietly does the wrong thing.
docker compose up -d db redis

echo "⏳ Waiting for PostGIS on :$HOST_DB_PORT and Redis on :$HOST_REDIS_PORT..."
until pg_isready -h localhost -p "$HOST_DB_PORT" -U mapsurvey >/dev/null 2>&1; do
    sleep 1
done
until docker compose exec -T redis redis-cli ping >/dev/null 2>&1; do
    sleep 1
done

# Run tests with proper environment
source env/bin/activate
SQL_ENGINE=django.contrib.gis.db.backends.postgis \
SQL_DATABASE=mapsurvey \
SQL_USER=mapsurvey \
SQL_PASSWORD=mapsurvey \
SQL_HOST=localhost \
SQL_PORT=$HOST_DB_PORT \
REDIS_URL=redis://localhost:$HOST_REDIS_PORT/1 \
python manage.py test "$@"
