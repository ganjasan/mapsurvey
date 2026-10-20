## Why

`sync_posthog_person_properties` copies each creator's labels from `survey_usercohort` (`segment`,
`plan`) plus `email_domain`, `is_freemail`, `ui_language` and first touch into PostHog person
properties, but only when someone runs it by hand. On 2026-10-20 PostHog had no `plan` value for
anyone although the database has carried `plan=pro` rows since 2026-09-18. Those properties now
gate the Replay Vision classifiers (*Plan segment* skips creators whose `segment` is set and paying
customers; *Creator intent* skips academic and private creators), so a stale sync means credits
spent on people we have already classified. Labels are written both through Django and by raw SQL
during the GTM review, so only a periodic run sees all of them (issue #371).

## What Changes

- `reclaim.sh`, the script the existing daily Render cron `mapsurvey-preview-media-reclaim` runs,
  ends with `python manage.py sync_posthog_person_properties`.
- That cron's block in `render.yaml` declares `POSTHOG_PROJECT_KEY` and `POSTHOG_API_HOST`
  (`sync: false`, set in the dashboard like the web service's).
- No new Render service, no application code change.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `product-analytics`: adds the requirement that creator person properties are re-synced daily
  without a manual run.

## Impact

- `reclaim.sh`, `render.yaml` (cron `mapsurvey-preview-media-reclaim`).
- Production: two environment variables to set on the cron in the Render dashboard; the first run
  after deploy pushes the current labels (a few hundred `posthog.set` calls).
