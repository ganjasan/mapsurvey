#!/bin/bash

# Development server script with hot-reload
# Usage: ./run_dev.sh [--clean]
#   --clean: Reset database to clean state

set -e

# Per-worktree port isolation: pick a PORT_OFFSET in .env.ports so multiple
# projects/worktrees can run dev + test in parallel without colliding on host
# ports. See .env.ports.example. Defaults to 0 (original ports) when unset.
[ -f .env.ports ] && source .env.ports
PORT_OFFSET="${PORT_OFFSET:-0}"
export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-mapsurvey}"
export HOST_DB_PORT=$((5434 + PORT_OFFSET))
export HOST_REDIS_PORT=$((6379 + PORT_OFFSET))
export HOST_WEB_PORT=$((8000 + PORT_OFFSET))

CLEAN=false

# Parse arguments
for arg in "$@"; do
    case $arg in
        --clean)
            CLEAN=true
            shift
            ;;
        *)
            echo "Unknown argument: $arg"
            echo "Usage: ./run_dev.sh [--clean]"
            exit 1
            ;;
    esac
done

# Clean database if requested
if [ "$CLEAN" = true ]; then
    echo "🗑️  Cleaning database..."
    docker compose down -v 2>/dev/null || docker-compose down -v 2>/dev/null
    echo "✓ Database volume removed"
fi

# Start database and Redis containers
echo "🐘 Starting PostgreSQL and Redis..."
docker compose up -d db redis 2>/dev/null || docker-compose up -d db redis 2>/dev/null

# Wait for database to be ready (check from host via mapped port)
echo "⏳ Waiting for database..."
until pg_isready -h localhost -p "$HOST_DB_PORT" -U mapsurvey 2>/dev/null; do
    sleep 1
done
echo "✓ Database ready"

# Activate virtual environment if exists
if [ -d "env" ]; then
    source env/bin/activate
fi

# Load .env file and override host/port for local development
while IFS='=' read -r key value; do
    # Skip comments and empty lines
    [[ "$key" =~ ^#.*$ || -z "$key" ]] && continue
    # Remove leading/trailing whitespace from key
    key=$(echo "$key" | xargs)
    # Export the variable
    export "$key=$value"
done < .env

export SQL_HOST=localhost
export SQL_PORT=$HOST_DB_PORT
export CELERY_BROKER_URL=redis://localhost:$HOST_REDIS_PORT/0
export CELERY_RESULT_BACKEND=redis://localhost:$HOST_REDIS_PORT/0
export REDIS_URL=redis://localhost:$HOST_REDIS_PORT/1

# Run migrations
echo "🔄 Running migrations..."
python manage.py migrate

# Create superuser if clean install
if [ "$CLEAN" = true ]; then
    echo "👤 Creating superuser..."
    python manage.py createsuperuser --noinput 2>/dev/null || echo "Superuser already exists or credentials not set"
fi

# Start Celery worker in background
echo "🔴 Starting Celery worker..."
celery -A mapsurvey worker -l info &
CELERY_PID=$!
echo "✓ Celery worker started (PID $CELERY_PID)"

cleanup() {
    echo ""
    echo "Stopping Celery worker..."
    kill $CELERY_PID 2>/dev/null
    wait $CELERY_PID 2>/dev/null
}
trap cleanup EXIT

# Start development server with hot-reload
echo ""
echo "🚀 Starting development server..."
echo "   http://localhost:$HOST_WEB_PORT"
echo "   Press Ctrl+C to stop"
echo ""

python manage.py runserver 0.0.0.0:$HOST_WEB_PORT
