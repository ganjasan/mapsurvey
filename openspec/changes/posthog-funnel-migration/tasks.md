# Tasks — funnel migration

Decisions taken 2026-08-15: **A** (backfill), card added, `survey_first_response` only (no
per-session events), DB access restored.

## 0. Decisions — settled

- [x] 0.1 Backfill, not forward-only.
- [x] 0.2 Paid plan enabled (card on file) so historical import is unlocked.
- [x] 0.3 All history. Earliest signup is **2026-02-18**; cohort labels and `SignupAttribution` are
      forward-only, so deep history has stages but thinner segmentation — stated, not a defect.
- [x] 0.4 `survey_first_response` only. A per-session event would put respondent-shaped data in
      PostHog, which is the boundary stage 1 drew.
- [x] 0.5 `MAPSURVEY_DB_URL` works again. **Measured volume, 1365 events:**
      registered 299 · activated 244 · survey_created 280 · question_added 229 ·
      published 121 · first_response 196. Far inside the 1M/month free tier.

## 1. Forward emission

- [x] 1.1 `survey/product_events.py` — event constants and a no-op-when-disabled `emit()`.
- [x] 1.2 `creator_registered` and `creator_activated_account` from `django_registration` signals,
      as separate receivers so analytics can never abort account creation.
- [x] 1.3 `survey_created` in `editor_views`, carrying `creation_method` from the start.
- [x] 1.4 `survey_question_added` on a survey's **first** question only — per-question emission
      would count questions rather than creators who got past the empty editor.
- [x] 1.5 `survey_published` on the real status transition, so the series stops being a proxy.
- [x] 1.6 `survey_first_response` via a `post_save` signal rather than three edits in `views.py`,
      one of which would eventually be missed. Attributed to the survey's owner, carrying only the
      survey id.
- [ ] 1.7 Record a real publish-transition timestamp on the model, so history can be re-derived
      exactly rather than from the creation proxy. Deferred: needs a migration, and 0048 is already
      claimed by the AI-generator branch.

## 2. Person properties

- [x] 2.1 `sync_posthog_person_properties` — `segment`, `plan`, `email_domain`, `is_freemail`,
      `date_joined` via `posthog.set()`.
- [x] 2.2 Kept out of the backfill entirely: PostHog #37000 applies `$set` regardless of timestamp,
      so a March event would clobber today's values. The backfill *refuses* to send `$set` rather
      than relying on care.
- [ ] 2.3 Define PostHog cohorts on those properties (project-side, after the first sync).

## 3. Backfill

- [x] 3.1 `backfill_posthog_events` — `historical_migration: true` on a **dedicated client**, so the
      setting can never reroute live traffic; deterministic uuid5 per (event, row); `--dry-run`,
      `--since`, `--limit`; oldest-first so a half-finished run leaves a complete prefix.
- [x] 3.2 Reuses `PUBLISHED_STATUSES` from `funnel.py` rather than restating it. A local copy would
      drift, and `archived` is easy to forget — omitting it understates the stage by 4 surveys today.
- [ ] 3.3 Run the dry-run against production and record the counts before sending.

## 4. Reconciliation — the acceptance criterion

- [x] 4.1 `check_posthog_funnel_parity` — dashboard and PostHog side by side per registration month,
      exits non-zero outside tolerance so it can gate a rollout instead of being read by eye.
      Counts distinct persons, and buckets by the person's registration month rather than the
      event's, matching `cohort_funnel()`.
- [ ] 4.2 Run it after the import; explain every difference or fix it.

## 5. Dashboard slimming — only after 4 passes

- [ ] 5.1 Replace the migrated blocks with links to PostHog.
- [ ] 5.2 Keep acquisition (GSC), worklists, cluster radar, abuse summary, goals.
- [ ] 5.3 Run both in parallel until the numbers are trusted.

## Found while doing this — not fixed here

- [ ] X.1 **`master` fails `makemigrations --check`**: `display_style` gained the `stars` choice
      without a regenerated migration. Choices/help_text only, so production is unaffected and no
      schema change is pending — but the check fails for everyone. Not fixed in this branch on
      purpose: migration `0048` is already taken by the AI-generator branch, and adding a second
      one here is exactly the numbering collision that keeps biting parallel worktrees.
