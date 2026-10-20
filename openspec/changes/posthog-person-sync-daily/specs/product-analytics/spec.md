## ADDED Requirements

### Requirement: Creator person properties are re-synced daily

The production daily cron SHALL run `sync_posthog_person_properties` once a day, after the
reclamation and billing steps, so that a label written to `survey_usercohort` by any path (Django,
admin or raw SQL) reaches the creator's PostHog person properties within a day without a manual
run. The cron SHALL receive `POSTHOG_PROJECT_KEY` and `POSTHOG_API_HOST` from the Render dashboard.

#### Scenario: A label written by SQL reaches PostHog
- **GIVEN** a creator's `plan` row is set to `pro` directly in the database
- **WHEN** the next daily cron run completes
- **THEN** that creator's PostHog person property `plan` is `pro`

#### Scenario: The sync runs last
- **WHEN** the daily cron script runs
- **THEN** `sync_posthog_person_properties` is invoked after `reclaim_preview_media`,
  `reclaim_orphan_uploads` and `notify_lapsed`

#### Scenario: Cron declares the PostHog configuration
- **WHEN** the Render Blueprint is read
- **THEN** the cron `mapsurvey-preview-media-reclaim` declares `POSTHOG_PROJECT_KEY` and
  `POSTHOG_API_HOST` with `sync: false`
