# Design — domain rules to the database

## Context

The user-cohorts change (2026-07-29) established: vocabulary in the database,
logic in code. `CURATED_DOMAIN_SEGMENTS` and `ACADEMIC_EXACT_DOMAINS` were placed
in code because they read like configuration for a rule engine. In a public
repository they read like a customer list.

The distinction that matters is not "data vs logic" but **"does this name a
specific customer"**. `.gov.uk → municipality` names no one; `agnewbeck.com →
consultancy` names a client we investigated.

## Goals

- No customer domain appears anywhere in the source tree or its tests.
- The production rule set stays reproducible without being committed.
- Classification cost does not regress: bulk runs stay one query, not one per user.

## Non-Goals

- Rewriting published history (separate operation).
- Changing cohort semantics, the dashboard, or assignment precedence.

## Decisions

### D1 — Split by "names a customer", not by "is data"

Stays in code (generic, publishable):

- `FREEMAIL_DOMAINS` — gmail, outlook, proton. Public knowledge, names nobody.
- `STUDENT_MARKERS` — `student.`, `alumnos.`, subdomain conventions.
- `SEGMENT_SUFFIX_RULES` — `.edu`, `.gov.uk`, `.ac.uk`, `.org`.
- `ACADEMIC_DOMAIN_PREFIXES` / `KEYWORDS` — `uni-`, `tu-`, `universit`.

Moves to the database:

- the curated organisation map (~25 domains),
- the academic exact-domain set (~15 domains) — these are individual
  universities, i.e. named customers, even though the segment is unsurprising.

### D2 — `DomainSegmentRule`, not a JSON blob on the dimension

A row per domain: `domain` (unique, lowercased), `cohort` (FK), `note`. Rows are
independent, searchable and editable one at a time in the admin, and a wrong rule
is corrected without touching the others. A JSON field would need the whole map
rewritten to change one entry and offers no admin affordance.

Domains are stored lowercased and matched exactly. No wildcard support: the
suffix rules in code already cover "everything under this TLD", and a wildcard
column would need precedence rules against them for no observed need.

### D3 — Precedence unchanged: exact rule, then student marker, then suffix

`classify_segment()` keeps its existing order, with the database standing where
the hard-coded map stood. So behaviour is identical for every domain that has a
rule, and the change is a pure relocation.

`classify_segment(email, domain_map=None)` takes an optional preloaded
`{domain: cohort_slug}`. `assign_cohorts` loads it once and passes it for every
user, so a 276-user run costs one query rather than 276. Called without it — one
user at a time, from the admin — it queries per call, which is correct and cheap.

### D4 — Rules are seeded from a local file, never a migration

A data migration carrying the domains would put them straight back into the
repository, which is the thing being fixed. Instead `assign_cohorts --rules-csv
<path>` upserts rules from a `domain,cohort,note` file kept in the gitignored
`docs/` tree, alongside the existing manual-label CSV. Production is populated by
running that command once; the file is the reproducible record.

Consequence, accepted: a fresh clone classifies nothing by curated domain until
someone loads the rules. The suffix rules still work, and the alternative is
publishing the list.

## Risks / Trade-offs

- **Rules can drift from any environment that lacks them.** A developer's local
  database will not reproduce production classification. Acceptable: the output
  is analytical, and the CSV is one command away.
- **History is unchanged by this.** The domains stay in commit `ac24b6b`, in the
  `refs/pull/44/head` ref GitHub keeps for the merged pull request, and in the
  PR description. This change removes them going forward only; the scrub is
  separate and has its own failure modes.

## Migration Plan

1. Schema migration for `DomainSegmentRule`.
2. Remove both lists from `survey/cohorts.py`; rewrite tests onto invented
   domains.
3. Write the real rule set to `docs/marketing/cohorts/domain-rules.csv`
   (gitignored) from the values currently in source.
4. On production: `assign_cohorts --rules-csv docs/marketing/cohorts/domain-rules.csv --apply`.
5. Verify the cohort breakdown on the dashboard is unchanged.

## Open Questions

- Should the freemail set also move? It names no customer and is genuinely
  generic, so no — but if the segment vocabulary ever grows a "personal" rule
  that depends on it, revisit.
