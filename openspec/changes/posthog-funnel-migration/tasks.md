# Tasks — funnel migration

**Nothing here is started. This change is an analysis awaiting a decision** — see proposal.md,
"Open questions for the decision". Specs are deliberately not written yet: option B would make most
of them wrong.

## 0. Decisions required before any work

- [ ] 0.1 **Backfill (A) or forward-only (B)?** Recommendation: A. Everything below assumes A.
- [ ] 0.2 Enable a paid PostHog plan (card on file). Historical import is gated on it; expected
      spend $0 at our volume.
- [ ] 0.3 How far back to import — all history, or from a date where segmentation is trustworthy?
- [ ] 0.4 One event per response session, or only `survey_first_response`? Design leans to the
      latter: per-session events edge toward the respondent boundary stage 1 drew.
- [ ] 0.5 Fix `MAPSURVEY_DB_URL` — the credential no longer authenticates, so the volume estimates
      in the proposal are structural rather than measured.

## 1. Forward emission (this is also stage 2)

- [ ] 1.1 Emit the five creator-lifecycle events from their views, each carrying `creation_method`
      and `timestamp_source: live`.
- [ ] 1.2 Record a real publish transition timestamp, so `survey_published` stops being a proxy.

## 2. Person properties

- [ ] 2.1 Send `segment`, `plan`, `email_domain`, `is_freemail`, `date_joined` on identify.
- [ ] 2.2 One-off pass setting them for existing users from current state — **never** as `$set` on a
      backfilled event (PostHog #37000 overwrites regardless of timestamp).
- [ ] 2.3 Define PostHog cohorts on those properties. The classification rules stay in our database;
      only the verdict travels.

## 3. Backfill

- [ ] 3.1 `manage.py backfill_posthog_events` — `historical_migration: true`, deterministic event
      uuids (idempotent), `--dry-run`, resumable, oldest-first.
- [ ] 3.2 Refuse to send `$set` while `historical_migration` is on, rather than relying on care.
- [ ] 3.3 Dry-run and record the counts per event type before sending anything.

## 4. Reconciliation — the acceptance criterion

- [ ] 4.1 Script printing PostHog funnel counts beside `CreatorFunnelService.cohort_funnel()` per
      registration month. **Agreement, or an explained difference, is what "done" means** — not a
      screenshot of a working import.
- [ ] 4.2 Apply the dashboard's own filters in the import: exclude staff/superusers, skip deleted
      sessions. Note `test_account_filters` already hides one account in PostHog insights.

## 5. Dashboard slimming — only after 4 passes

- [ ] 5.1 Replace the stage funnel, cohort funnel, time-to-value, active/dormant and weekly charts
      with links to the PostHog dashboard.
- [ ] 5.2 Keep acquisition (GSC), worklists, cluster radar, abuse summary, goals where they are.
- [ ] 5.3 Run both in parallel until the numbers are trusted; deleting the local computation first
      would leave no way to tell which one is wrong.
