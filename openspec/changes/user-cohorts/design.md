# Design — user cohorts

## Context

`survey/funnel.py::CreatorFunnelService` already aggregates the creator funnel
over live tables (no event log, no backfill) and renders it into a staff-only
admin dashboard via the `FunnelReport` proxy model. It has two proto-segmentation
signals already: `FREEMAIL_DOMAINS` (institutional-vs-freemail) and
`cluster_radar()` (temporal bursts + same-domain groups). Both are heuristics
computed per request and discarded; neither is a persisted classification a human
can correct.

Production shape as of 2026-07-29 (275 non-staff users):

| Signal | Count |
|---|---|
| Non-freemail domain (domain carries a segment signal) | 81 |
| Freemail **with** a dossier under `docs/marketing/user-outreach/` | 58 |
| Freemail with no dossier | 136 (65 of them have activity) |
| gmail.com alone | 167 |
| One course cluster on 2026-05-11/12 | 73 registrations |

So ~139 users are classifiable today (domain or dossier), and any design that
relies on derivation alone permanently loses the majority.

## Goals

- Cohorts are **data, not code**: a new segment or a whole new axis is created in
  the admin, not in a migration.
- A user has at most one cohort per axis, so "share of registrations by segment"
  sums to 100% without double counting.
- Human judgement wins: an automatic rule may propose, never overwrite.
- Re-running classification is idempotent and safe on production.

## Non-Goals

- Entitlements/billing (see proposal Non-Goals).
- Multi-label cohorts within one dimension (a user is not both University and
  Municipality — if that need appears, add a second dimension).
- Historical cohort membership over time; the assignment is current-state only.

## Decisions

### D1 — Dimension + Cohort + assignment, not enum fields

`CohortDimension(slug, name, order)` → `Cohort(dimension, slug, name, color,
description, order)` → `UserCohort(user, cohort, source, note, assigned_at)`.

Rejected: `CharField(choices=…)` on a profile model (every new segment is a code
change plus a migration; a third axis cannot be added without rewriting), and
`auth.Group` (already means *permissions*; overloading it with analytics risks a
future `has_perm` accident, and it carries no dimension grouping, colour or
description).

Uniqueness is enforced on **(user, dimension)**, not (user, cohort). Since
`UserCohort` points at `Cohort`, the dimension is denormalised onto the
assignment row as a FK so the DB constraint is expressible; `save()` keeps it in
sync with `cohort.dimension` (and validates the pair) rather than trusting the
caller.

### D2 — `source` field: rules propose, humans decide

`UserCohort.source ∈ {auto, manual}`. The classifier only ever creates or
updates rows with `source='auto'`; a row with `source='manual'` is skipped
entirely. Staff assignment always writes `source='manual'`. This makes the
management command re-runnable after every signup wave without erasing curated
labels — the single most important property, since 60% of the base can only ever
be labelled by hand.

### D3 — Classification rules are a data-driven table, not per-user heuristics

`survey/cohorts.py` holds an ordered rule list evaluated against the email
domain:

1. exact domain map (curated: `decisio.nl → consultancy`, `senmvku.berlin.de →
   government`, `migcom.com → consultancy`, …),
2. suffix rules (`.edu`, `.ac.uk`, `.edu.eg`, `.edu.au`, `uni-*.de`, `student.*`
   → education; `.gov`, `.gov.uk`, `.gov.au`, `.or.tz` → government),
3. freemail → no proposal (explicitly *not* "individual" — absence of signal is
   not evidence of a segment; leaving them unassigned keeps the "unclassified"
   number honest on the dashboard).

Rules live in code (they are logic, reviewed in PRs), while cohorts live in the
DB (they are vocabulary). The curated domain map is the seam where the two meet
and is deliberately small and explicit.

### D4 — Seeded vocabulary reflects observed reality, not aspiration

The seed migration creates two dimensions:

- **Plan**: `free`, `pro`. Everyone starts unassigned; `pro` is applied by hand
  once a deal exists. Deliberately *not* defaulting everyone to `free` — an
  unassigned user is "not yet judged", which is different from "judged free".
- **Segment**: `university` (staff/researchers), `student-cohort` (course
  clusters — the 73-registration May wave is one course, not 73 institutions),
  `municipality` (city/regional government, B2G), `consultancy` (planning,
  mobility and engineering firms — the "Аналитики" the funnel actually converts),
  `ngo` (associations, community groups, activists), `business` (commercial
  non-consultancy: energy, housing, real estate), `individual` (hobby, personal,
  friends-and-family use).

`student-cohort` is split from `university` on purpose: the two share a domain
but have opposite commercial value — a lecturer is a repeatable channel, a
student is a one-semester burst.

### D5 — Dashboard: breakdown table per dimension, reusing the funnel service

`CreatorFunnelService.cohort_breakdown()` returns, per dimension, one row per
cohort plus an explicit **Unclassified** row, each with users / created /
published / collecting / responses and the same `_tone`-style percentages the
existing blocks use. It is computed from the same stage-membership sets the
funnel already builds (`_created_uids`, `_published_uids`, `_response_counts`),
so cohort slicing costs one extra query (the `UserCohort` map), not a second
funnel pass.

Rendered as a new section ③ "Audience mix" in `admin/funnel_dashboard.html`,
placed after the weekly panels (which hold the cluster radar) and before the
monthly cohort funnel: the radar detects *unlabelled* clusters, the breakdown
reports the *labelled* ones, so they read in that order. The existing "Cohort
funnel" heading is renamed "Monthly cohort funnel" so the two senses of the word
cohort — registration month vs. audience label — stay distinguishable.

## Risks / Trade-offs

- **Stale labels.** A user's segment is a snapshot; nothing re-checks it. Accepted
  — the alternative (versioned membership) buys nothing at 275 users. The
  `assigned_at` timestamp makes staleness visible.
- **Unclassified stays large.** With 136 freemail-without-dossier users, the
  Unclassified row will dominate at first. That is the honest reading, and it is
  itself the metric: "% of the base we can name" is a GTM number worth watching.
- **Curated domain map drifts.** Every new institutional domain needs a code
  edit or a manual assignment. At current signup volume (~35/month) this is
  cheap; if it stops being cheap, promote the map to a DB table.

## Migration Plan

1. Schema migration for the three models.
2. Data migration seeding the two dimensions and their cohorts (idempotent
   `get_or_create` by slug; reverse leaves data alone).
3. `python manage.py assign_cohorts` (dry-run by default) classifies existing
   users from their domain. Production run is a one-off; afterwards it can be
   re-run at will thanks to D2.
4. `python manage.py assign_cohorts --from-csv
   docs/marketing/cohorts/segment-manual-2026-07-29.csv --apply` labels the
   freemail users the dossiers already identify. Anything the dossiers cannot
   name stays unclassified, and the admin bulk action covers the rest (notably
   the May course cluster, which is a date-range filter plus one action).

## Open Questions

- Should `Plan` eventually be derived from a real subscription record once
  billing exists? Likely yes — at that point the `plan` dimension becomes a
  read-only projection and `source` grows a third value (`billing`). Out of scope
  here, but the `source` field is shaped to absorb it.
