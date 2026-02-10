#!/bin/bash

# Development server script with hot-reload
# Usage: ./run_dev.sh [--clean]
#   --clean: Reset database to clean state

set -e

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

# Start database container
echo "🐘 Starting PostgreSQL..."
docker compose up -d db 2>/dev/null || docker-compose up -d db 2>/dev/null

# Wait for database to be ready (check from host via mapped port)
echo "⏳ Waiting for database..."
until pg_isready -h localhost -p 5434 -U mapsurvey 2>/dev/null; do
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
export SQL_PORT=5434

# Run migrations
echo "🔄 Running migrations..."
python manage.py migrate

# Create superuser if clean install
if [ "$CLEAN" = true ]; then
    echo "👤 Creating superuser..."
    python manage.py createsuperuser --noinput 2>/dev/null || echo "Superuser already exists or credentials not set"
fi

# Start development server with hot-reload
echo ""
echo "🚀 Starting development server..."
echo "   http://localhost:8000"
echo "   Press Ctrl+C to stop"
echo ""

python manage.py runserver 0.0.0.0:8000
