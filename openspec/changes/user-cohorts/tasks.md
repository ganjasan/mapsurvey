# Tasks — user cohorts

## 1. Models + migrations

- [x] Add `CohortDimension`, `Cohort`, `UserCohort` to `survey/models.py`
      (slugs, ordering, colour/description; `UserCohort.source` in
      `{auto, manual}`, `assigned_at`, denormalised `dimension` FK).
- [x] `UniqueConstraint(user, dimension)` on `UserCohort`;
      `UniqueConstraint(dimension, slug)` on `Cohort`.
- [x] `UserCohort.save()` sets `dimension` from `cohort.dimension`.
- [x] Schema migration.
- [x] Data migration seeding dimensions `plan` (free, pro) and `segment`
      (university, student-cohort, municipality, consultancy, ngo, business,
      individual) via idempotent `get_or_create`.

## 2. Classification rules

- [x] New `survey/cohorts.py`: `FREEMAIL_DOMAINS` reuse from `funnel.py`,
      `CURATED_DOMAIN_SEGMENTS` exact map, `SEGMENT_SUFFIX_RULES` ordered list,
      `classify_segment(email) -> slug | None`.
- [x] `assign_cohort(user, cohort, source, note='')` helper — replaces within
      dimension, refuses to touch `manual` rows when `source='auto'`.

## 3. Management command

- [x] `survey/management/commands/assign_cohorts.py` — dry run by default,
      `--apply` to write, prints per-cohort counts and the unclassified total.
- [x] `--from-csv PATH` applies a curated `username,cohort[,note]` list as manual
      assignments; unknown users/cohorts are reported and skipped.
- [x] Ship the curated list derived from the dossiers as
      `docs/marketing/cohorts/segment-manual-2026-07-29.csv`.

## 4. Admin

- [x] Register `CohortDimension` (inline cohorts), `Cohort`, `UserCohort`.
- [x] Bulk action on the user changelist: choose a cohort → assign to selected
      users with source `manual` (intermediate confirmation page).
- [x] Show current cohorts as a read-only column/filter on the user changelist.

## 5. Dashboard

- [x] `CreatorFunnelService.cohort_breakdown()` — per dimension, per cohort:
      users / created / published / collecting / responses + unclassified row,
      reusing the existing stage-membership sets.
- [x] Add to `dashboard_context()`.
- [x] Render a breakdown block in `admin/funnel_dashboard.html` as section ③
      ("Audience mix"), between the weekly panels and the monthly cohort funnel,
      styled like the existing tables; renumber the sections below it.

## 6. Tests (GIVEN/WHEN/THEN)

- [x] Uniqueness: one cohort per dimension; reassignment replaces; slug unique
      within dimension only.
- [x] `save()` derives dimension from cohort.
- [x] Classification: `.edu` / `.gov.uk` / curated domain / freemail / malformed
      email.
- [x] `auto` never overwrites `manual`; `auto` updates its own row; manual
      overrides auto.
- [x] Command: dry run writes nothing; second apply is a no-op.
- [x] Breakdown: rows + unclassified sum to total registrations; empty dimension
      renders; activation counted per cohort.

## 7. Production classification pass

- [ ] Run `assign_cohorts` dry-run against prod, review, then `--apply`.
- [ ] Manual pass over freemail-with-dossier users from
      `docs/marketing/user-outreach/` via the admin bulk action.
