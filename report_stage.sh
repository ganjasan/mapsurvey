#!/bin/sh
# Daily report-stage pass (Render cron mapsurvey-report-stage runs this).
# A shell script, not an inline command list: Render's dockerCommand does not go
# through a shell (see reclaim.sh). Scores every live survey, records the
# signals, mails the owner one digest when something fired. Exits non-zero when
# the digest could not be sent, so Render shows the failed run.
set -e
python manage.py detect_report_stage
