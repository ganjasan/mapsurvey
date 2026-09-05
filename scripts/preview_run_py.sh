#!/bin/sh
# Run a Python snippet inside `manage.py shell` on a Render PR preview via a
# one-off job. Jobs get no shell (quotes, pipes, && are plain arguments), so the
# snippet travels base64-encoded as the single positional argument:
#
#   sh scripts/preview_run_py.sh <base64 of the python source>
#
# Preview databases are disposable; never point this at production.
set -e
[ -n "$1" ] || { echo "usage: preview_run_py.sh <base64 python>" >&2; exit 1; }
echo "$1" | base64 -d > /tmp/preview_run.py
python manage.py shell < /tmp/preview_run.py
