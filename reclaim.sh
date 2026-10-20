#!/bin/sh
# Daily reclamation pass (Render cron mapsurvey-preview-media-reclaim runs this).
# A shell script, not an inline command list: Render's dockerCommand does not go
# through a shell, so `a && b` there becomes arguments to `a` (recorded lesson).
#
# Order matters loosely: preview media first (bigger objects), then orphaned
# respondent uploads, then lapsed-Pro mail, then the PostHog person sync. Each
# command is independently safe to rerun and exits cleanly when it has nothing
# to do.
set -e
python manage.py reclaim_preview_media --delete
python manage.py reclaim_orphan_uploads --delete

# Pro subscriptions whose paid period ended since the last run: one
# plan_lapsed event and one email per owner (billing app).
python manage.py notify_lapsed

# Creator labels (segment, plan, domain, language) to PostHog person properties.
# Last on purpose: set -e stops the script at the first failure, and a PostHog
# outage or a missing key must never block reclamation or lapse mail. Labels are
# also written by raw SQL during the GTM review, which is why this is a daily
# pass and not a save signal (openspec: posthog-person-sync-daily, #371).
python manage.py sync_posthog_person_properties
