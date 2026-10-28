## Why

The funnel dashboard measures the creator lifecycle in aggregate — 275 real
registrations, 144 with a survey, 42 published, 102 collecting responses. What it
cannot answer is **who** those creators are. Two questions drive current GTM
decisions and neither is answerable today:

- **Commercial**: which creators would sit on a paid tier vs. the free channel
  (the 2026-07-29 monetization pivot sells Pro as a project line item, so we need
  to size the Pro-shaped population *before* billing exists).
- **Audience**: which segments actually use the product — universities, course
  cohorts, municipalities, planning consultancies, NGOs — so landing pages,
  pricing and outreach target the segments that convert rather than the ones we
  assume.

Today this knowledge lives only in 125 hand-written dossiers under
`docs/marketing/user-outreach/`, in prose, unqueryable and drifting from the DB.
Email domain alone is not a substitute: **167 of 275 creators use gmail.com**, so
a purely derived classification leaves 60% of the base unlabelled forever.

This change introduces cohorts as **analytical labels only** — no entitlements,
no gating, no billing. Marking a user "Pro" grants nothing; it records a
judgement so the dashboard can slice the funnel by it.

## What Changes

- New cohort vocabulary in the database: `CohortDimension` (an axis, e.g. *Plan*,
  *Segment*) owning `Cohort` values (e.g. *Free* / *Pro*; *Universities* /
  *Municipalities* / *Consultancies* / …). Both are staff-editable data — adding
  a segment or a whole new dimension needs no migration.
- New `UserCohort` assignment, unique per (user, dimension): a user holds at most
  one cohort per axis. Each assignment records whether it came from an automatic
  rule or a human, and manual assignments are never overwritten by rules.
- Automatic classification from the email domain (institutional TLDs and a
  curated domain map) proposes cohorts for the ~40% of users whose domain carries
  a signal; a management command applies it in bulk and is safe to re-run.
- Staff UI: cohorts and dimensions in Django admin, plus a bulk "assign cohort"
  action on the user list so freemail users can be labelled by hand from dossier
  knowledge.
- Funnel dashboard gains a cohort breakdown: for every dimension, each cohort's
  share of registrations, activation (created / published / collecting) and
  responses, so the existing funnel can be read per segment and per plan.

## Capabilities

### New Capabilities

- **user-cohorts**: define cohort dimensions and cohorts, assign at most one
  cohort per dimension to a user (manually or by rule), and report the creator
  funnel broken down by cohort.

## Non-Goals

- No billing, subscription, payment or entitlement logic. `Plan = Pro` is a label
  a human sets, not a purchased state, and grants no feature access.
- No self-service: cohorts are staff-only and invisible to end users.
- No back-porting of cohorts into `docs/marketing/user-outreach/` dossiers; the
  dossiers stay the narrative record, the DB becomes the queryable one.
