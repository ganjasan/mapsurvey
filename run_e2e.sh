#!/bin/bash
# Run the Playwright end-to-end suite against the locally running dev server.
#
# Pre-requisite: dev server is up (`./run_dev.sh` in another terminal).
#
# Usage:
#   ./run_e2e.sh                 # default: headless, fast
#   ./run_e2e.sh --visible       # show the browser window
#   ./run_e2e.sh --visible --slow # show the browser AND slow it down to 500 ms/action
#   ./run_e2e.sh --debug         # opens Playwright Inspector for step-by-step debugging
#   ./run_e2e.sh -k <pattern>    # forwarded to pytest, e.g. -k satellite
#
# Any flag we don't recognize is passed straight through to pytest.

set -e

# Per-worktree port isolation (see .env.ports.example). Point the suite at this
# worktree's dev server + DB so it doesn't hit another worktree's instance.
[ -f .env.ports ] && source .env.ports
PORT_OFFSET="${PORT_OFFSET:-0}"
export HOST_DB_PORT=$((5434 + PORT_OFFSET))
export HOST_WEB_PORT=$((8000 + PORT_OFFSET))

VISIBLE=false
SLOW=false
DEBUG=false
PASSTHROUGH=()

for arg in "$@"; do
    case $arg in
        --visible|-V)
            VISIBLE=true
            ;;
        --slow|-S)
            SLOW=true
            ;;
        --debug|-D)
            DEBUG=true
            ;;
        *)
            PASSTHROUGH+=("$arg")
            ;;
    esac
done

PYTEST_ARGS=(tests_e2e/ -v)

if [ "$VISIBLE" = true ]; then
    PYTEST_ARGS+=(--headed)
fi

if [ "$SLOW" = true ]; then
    PYTEST_ARGS+=(--slowmo=500)
fi

# Source the venv if present
if [ -d "env" ]; then
    # shellcheck disable=SC1091
    source env/bin/activate
fi

# Live dev DB connection (matches run_dev.sh)
export SQL_HOST=localhost
export SQL_PORT=$HOST_DB_PORT
export E2E_BASE_URL="${E2E_BASE_URL:-http://localhost:$HOST_WEB_PORT}"
export DJANGO_ALLOW_ASYNC_UNSAFE=true
export DJANGO_SETTINGS_MODULE=mapsurvey.settings

if [ "$DEBUG" = true ]; then
    # PWDEBUG=1 opens Playwright Inspector; implies --headed
    export PWDEBUG=1
fi

echo "→ pytest ${PYTEST_ARGS[*]} ${PASSTHROUGH[*]}"
exec pytest "${PYTEST_ARGS[@]}" "${PASSTHROUGH[@]}"
