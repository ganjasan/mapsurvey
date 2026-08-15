#!/bin/sh
# Render pre-deploy: runs after the new image is built, while the previous version is
# still serving. Anything that must happen before the new code goes live belongs here,
# not in entrypoint.sh — the entrypoint runs inside the 502 window (the web service
# mounts a disk, so Render cannot run old and new instances side by side).
#
# This exists as a script because Render does NOT run preDeployCommand through a shell:
# `migrate && createsuperuser || true` in render.yaml was parsed as arguments to migrate
# and failed with "unrecognized arguments: manage.py createsuperuser || true". A script
# is the reliable way to express more than one command, and it can be tested locally.
#
# `set -e`: a failing migration must fail the pre-deploy, which aborts the deploy and
# leaves the current version serving.
set -e

python manage.py migrate

# Idempotent bookkeeping: fails once the user exists, which is not a deploy failure.
if [ -n "$DJANGO_SUPERUSER_USERNAME" ]; then
    python manage.py createsuperuser --noinput || true
fi
