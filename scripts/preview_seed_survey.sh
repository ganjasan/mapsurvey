#!/bin/sh
# Seed a Render PR preview with a survey from a structure ZIP, via a one-off job.
#
# Render runs a job's startCommand WITHOUT a shell (quotes, pipes and && become
# plain arguments — the same trap as preDeployCommand), so everything that needs
# quoting lives in this file and the job only passes positional arguments:
#
#   sh scripts/preview_seed_survey.sh <base64 of the ZIP> [survey uuid] [org name]
#
# Creates the dev admin (admin / adminadmin — a preview database is disposable),
# an organisation, imports the ZIP through the normal import path (same validation
# as the editor's /editor/import/), publishes the survey and prints its UUID.
set -e
SEED_B64="$1"
SEED_UUID="${2:-}"
SEED_ORG="${3:-Preview workspace}"
[ -n "$SEED_B64" ] || { echo "usage: preview_seed_survey.sh <base64 zip> [uuid] [org]" >&2; exit 1; }
echo "$SEED_B64" | base64 -d > /tmp/seed_survey.zip
export SEED_UUID SEED_ORG
python manage.py shell <<'PY'
import os, uuid
from django.contrib.auth.models import User
from survey.models import Organization, Membership
from survey.serialization import import_survey_from_zip
user, _ = User.objects.get_or_create(username='admin', defaults={'email': 'admin@example.com'})
user.set_password('adminadmin'); user.is_superuser = user.is_staff = True; user.save()
org, _ = Organization.objects.get_or_create(name=os.environ['SEED_ORG'])
Membership.objects.get_or_create(user=user, organization=org, defaults={'role': 'admin'})
survey, warnings = import_survey_from_zip(open('/tmp/seed_survey.zip', 'rb'), organization=org, created_by=user)
for w in warnings:
    print('WARNING', w)
if os.environ.get('SEED_UUID'):
    survey.uuid = uuid.UUID(os.environ['SEED_UUID'])
survey.status = 'published'
survey.save()
print('SEEDED', survey.uuid, survey.name)
PY
