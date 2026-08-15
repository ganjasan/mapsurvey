# Design — moving the growth funnel to PostHog

Assumes option A from the proposal (backfill). If B is chosen instead, sections 3–5 fall away and
what remains is stage 2 by another name.

## 1. The event taxonomy

Five creator-lifecycle events, each derivable from a timestamp that already exists in the database.
That constraint is deliberate: an event we cannot reconstruct historically would give the funnel a
step that is empty before today and break the comparison the whole exercise is for.

| Event | Historical source | Emitted forward by |
|---|---|---|
| `creator_registered` | `auth_user.date_joined` | registration view |
| `creator_activated_account` | `auth_user.is_active` + activation flow | activation view |
| `survey_created` | `SurveyHeader.created_at` | survey create view |
| `survey_question_added` | first `Question` on the creator's survey | question create |
| `survey_published` | `SurveyHeader.created_at` of a published survey — **approximate** | publish action |
| `survey_first_response` | `min(SurveySession.start_datetime)` per survey | response ingest |

**`survey_published` is the weak one and must be labelled as such.** We have no publish-transition
timestamp; `_published_first_created` (`funnel.py:128`) already uses survey *creation* time as the
proxy and the existing design admits it. Backfilled events inherit that error. Forward-emitted ones
will be exact, which means the series has a discontinuity at cutover. Carry a property
`timestamp_source: backfill_proxy | live` so any insight can exclude the approximate half rather
than silently averaging the two.

Every event carries `creation_method: ai | manual` from the start — the field that makes the AI
generator measurable. Historical events are all `manual` by definition, which is exactly the baseline
we want.

## 2. Person properties and cohorts

`distinct_id` stays the user pk, matching the snippet from stage 1 — that is what makes a backfilled
`survey_created` from March land on the same person as today's `$pageview`.

Person properties to set: `segment`, `plan` (from `UserCohort`), `email_domain`, `date_joined`,
`is_freemail`. PostHog cohorts are then defined *on those properties* rather than duplicating the
classification logic. The rules stay in our database and only their verdict travels.

**Cohorts get strictly better by moving.** Today `cohort_breakdown` renders on one admin page. As
person properties they filter every insight, every session recording, every future experiment — a
university-vs-consultancy split of the activation funnel becomes a dropdown rather than a code
change.

## 3. Backfill mechanics

`POST /batch/` with `historical_migration: true`, chunks well under the 20MB body cap, driven by a
management command (`python manage.py backfill_posthog_events [--dry-run] [--since] [--limit]`).

Non-negotiable properties of that command:

- **Idempotent.** Deterministic `uuid` per (user, event, source row) so a re-run does not double
  every historical stage. This is the difference between a repeatable migration and a one-shot we
  are afraid to touch.
- **Dry-run first**, printing counts per event type, so the volume is known before anything is sent.
- **Resumable**, because a half-finished import that cannot be continued is worse than none.

### The trap: `$set` during historical migration

PostHog issue [#37000](https://github.com/PostHog/posthog/issues/37000) — during a historical
migration, `$set` overwrites person properties **regardless of the event's timestamp**. A backfilled
March event carrying `$set` would clobber a person's current properties with March's values.

Therefore: **backfilled events carry no `$set` at all.** Person properties are written once, in a
separate forward-dated pass, from current database state. The two must not be mixed, and the command
should refuse to send an event with `$set` when `historical_migration` is on rather than trusting
the author to remember.

### Ordering

Import oldest-first so that if the run dies halfway, what exists in PostHog is a complete prefix of
history rather than a scatter.

## 4. Verification — how we know the numbers are right

The failure mode is a migration that looks finished and is quietly wrong. So the acceptance test is
not "the import ran" but **"PostHog and the admin dashboard agree"**:

For each registration-month cohort, PostHog's funnel step counts must match
`CreatorFunnelService.cohort_funnel()` within a stated tolerance, and any disagreement must be
explainable (deleted surveys, staff exclusion, the publish proxy). A reconciliation script that
prints both columns side by side, like the version-filter-parity change did, is the deliverable —
not a screenshot.

Known sources of legitimate divergence, to state up front:
- The dashboard excludes `is_staff`/`is_superuser`; the import must apply the same filter.
- The dashboard counts non-deleted sessions; deleted ones must be skipped identically.
- PostHog's `test_account_filters` already excludes `konuchovartem@gmail.com` — insights will differ
  from raw SQL by that account unless the filter is off.

## 5. What happens to the admin dashboard

It shrinks rather than disappears, and only after reconciliation passes:

- **Keeps**: acquisition (GSC), worklists, cluster radar, abuse summary, goals.
- **Loses**: the stage funnel, cohort funnel, time-to-value, active/dormant, weekly charts — replaced
  by links to the PostHog dashboard.
- **Interim**: both run in parallel. Deleting the local computation before the numbers are trusted
  would leave no way to tell which is wrong.

## Risks

- **Silent divergence.** Mitigated by the reconciliation script being the acceptance criterion.
- **The publish proxy** poisons any "time to publish" metric across the cutover. Mitigated by
  `timestamp_source`, and properly fixed only by recording a real publish transition — worth doing
  as part of stage 2 regardless.
- **A card on file.** Historical import needs a paid plan enabled. Expected spend $0, but it is a
  commercial decision.
- **One-way door on person properties.** Backfilled person data is awkward to unpick; get `segment`
  right before the pass, or accept re-running it.
- **`SignupAttribution` and cohort labels are forward-only** — deep history will have stages but
  weaker segmentation. Not a defect, but it will look like one on a chart unless stated.

## Open questions

1. Is `survey_published`'s proxy acceptable for history, or do we only trust publish from cutover?
2. Do we import respondent *counts* as `survey_first_response` only, or one event per session? The
   latter is ~4.5k events and enables response-volume trends in PostHog; the former is lighter and
   keeps respondent-shaped data out of PostHog entirely. **Leaning to the former** — respondent
   sessions are the customers' data, and a per-session event in PostHog edges toward the boundary
   stage 1 drew.
3. Same question for `SurveyEvent`: not imported, ever. Confirm.
