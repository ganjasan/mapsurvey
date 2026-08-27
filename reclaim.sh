#!/bin/sh
# Daily reclamation pass (Render cron mapsurvey-preview-media-reclaim runs this).
# A shell script, not an inline command list: Render's dockerCommand does not go
# through a shell, so `a && b` there becomes arguments to `a` (recorded lesson).
#
# Order matters loosely: preview media first (bigger objects), then orphaned
# respondent uploads. Each command is independently safe to rerun and exits
# cleanly when it has nothing to do.
set -e
python manage.py reclaim_preview_media --delete
python manage.py reclaim_orphan_uploads --delete
