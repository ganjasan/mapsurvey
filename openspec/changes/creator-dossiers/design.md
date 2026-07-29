# Design — creator dossiers

## Context

The user-cohorts change (2026-07-29) put the *classification* of creators into
the database and left the *evidence* for it on disk. `survey/models.py` now has a
small cluster of per-user analytics records — `SignupAttribution` (where they came
from), `UserActivity` (when they were last seen), `UserCohort` (what they are) —
and this change adds the fourth: what we know about them.

What the source material actually looks like, measured across the 125 dossiers:

| Header field | Present in |
|---|---|
| Email | 119 |
| Username | 114 |
| Tier | 40 |
| Organization | 29 |
| Role | 22 |
| Location | 19 |
| Web | 9 |
| LinkedIn | 6 |

Plus 94 `correspondence/*.md` files, 36 of which carry a `SENT` marker.

The shape of that table is the central design fact: **structured headers are the
exception, prose is the rule.** Any design that leans on parsing loses most of
the content.

## Goals

- The knowledge survives the laptop and sits next to the cohort it explains.
- Relationship history is append-only and legible in date order.
- Exit to a CRM is a file handover, not a re-typing project.
- Import never touches the source files, and can be run repeatedly while it is
  being tuned.

## Non-Goals

- Pipeline/deal mechanics (see proposal Non-Goals).
- Round-tripping edits back into markdown.
- Parsing the prose into structure beyond the handful of labelled headers.

## Decisions

### D1 — Two models: flat profile, append-only notes

`CreatorProfile` (OneToOne → user) holds the facts we look up repeatedly and that
a CRM has columns for: `organization`, `role`, `country`, `linkedin_url`,
`website`, `how_found_us`, `summary`. `CreatorNote` (FK → user) holds dated
entries with `author`, `kind`, `body`.

Rejected: a single `notes` TextField on the profile. It cannot express "when did
we last talk to them", every edit overwrites the previous state, and a CRM import
would see one opaque blob where it expects Activities.

Rejected: modelling organisations as their own table. Tempting — several
creators share an employer (a couple of firms have two or three accounts) — but an org table
needs dedup rules, merge handling and a canonical-name policy to be worth
anything, and at 276 users a free-text `organization` plus the existing email
domain answers the same questions. Revisit when a real CRM defines the schema.

### D2 — Notes are append-only by convention, enforced for tooling

The importer and any future automation only ever *create* notes; they never
update or delete. Staff can still correct a note in the admin — a typo should be
fixable — but nothing automated rewrites history, so the timeline stays a record
of what was known when. This is the same discipline `AuditLog` follows, without
the append-only hard guarantee, because these are working notes rather than an
audit trail.

`kind` is a small fixed vocabulary (`research`, `email`, `call`, `signal`) rather
than free-form tags: four values map cleanly onto CRM activity types, and an open
vocabulary would fragment within a month.

### D3 — Import: headers into columns, everything else into one research note

The importer walks `docs/marketing/user-outreach/<username>/`:

1. Matches the directory to an account: first the directory name against
   `auth_user.username` case-insensitively (plus `_`/`.` and leading-`@`
   variants), then any email address in the dossier header.

   The fallback is not optional. Directory names drift badly from account names —
   `j_okafor` is `j.okafor.2@example.edu`, `roseb` is `RoseB.`, `mbrito7` is
   `mbrito7@example.com`. Measured on the real tree: **name alone matches 85 of
   125; adding the email match reaches 123.** The two that remain are a batch
   working file and a company-level dossier, neither of which describes a single
   account.

   Group dossiers (`ftspk_class`, `mora_group`) contain several members' emails
   and will attach to whichever member matches first. Accepted: one member
   carrying the group's story beats losing it, and the note names the group in
   its first line. Unmatched directories are reported, never guessed at.
2. Reads labelled headers (`Organization`, `Role`, `Location`, `Web`,
   `LinkedIn`, plus a LinkedIn URL found anywhere in the body) into the profile
   columns. Absent labels stay empty; nothing is inferred from prose.
3. Stores the **entire** `profile.md` body as one `research` note. This is the
   decision that preserves the value: 96 of 125 dossiers have no Organization
   header, and their worth is in the paragraphs underneath.
4. Turns each `correspondence/*.md` into an `email` note, taking the date from
   the `YYYY-MM-DD` filename prefix and preserving the `SENT` marker in the body
   verbatim.

`Tier` is deliberately **not** imported. It is a stale hand-maintained duplicate
of what the funnel dashboard computes live, and copying it into the database
would resurrect the exact disagreement this change exists to end.

### D4 — Idempotence via a source key, not content hashing

Each imported note records `source_path` (repo-relative). Re-running the importer
skips any note whose `source_path` already exists for that user. Consequences,
accepted deliberately: editing a dossier after import does **not** update the
note, and re-importing after a rename creates a duplicate. Both are visible and
correctable by hand; the alternative (content hashing, update-in-place) conflicts
with D2's append-only stance and would let a tool rewrite history.

Profile columns *are* updated on re-run, but only where the incoming value is
non-empty — so a hand-corrected organisation is not blanked by a dossier that
never had the header.

### D5 — CSV export as both CRM exit and GDPR answer

One command emits two files: `profiles.csv` (one row per creator, structured
columns plus cohort and activity figures the funnel already computes) and
`notes.csv` (one row per note, with username, date, kind, author, body). Every
CRM ingests this shape, and the same command filtered to one user answers a
subject access request. Building the export now, rather than "when we pick a
CRM", is what makes the storage decision reversible.

## Risks / Trade-offs

- **Import fidelity.** The prose lands as one undifferentiated note per dossier.
  Structure inside it (use case, research notes, next steps) is not extracted.
  Accepted: the alternative is a bespoke parser for 125 inconsistent files, and
  the note is searchable regardless.
- **Two sources of truth during transition.** Files remain on disk after import.
  Mitigated by declaring the DB authoritative in the proposal and updating the
  `/user-outreach` workflow to write to the DB; the files become an archive.
- **Personal data now on production.** See proposal Privacy. The export command
  and admin deletion are the operational answer; the design does not pretend the
  risk away.
- **Unmatched dossiers.** Directories that match no user (people who never
  registered, renamed accounts) simply do not import. The command reports them so
  the tail is visible rather than silently dropped.

## Migration Plan

1. Schema migration for both models.
2. `python manage.py import_dossiers docs/marketing/user-outreach/` (dry run) —
   review the match report, especially unmatched directories.
3. Same command with `--apply`.
4. `python manage.py export_creators` to verify the CRM exit path works on real
   data.
5. Update the `/user-outreach` command so new research is written to the DB.

## Open Questions

- When a real CRM is chosen, does it become the source of truth and this a
  read-only mirror, or does the DB stay primary with periodic export? Deferred:
  the answer depends on whether the CRM can hold the product-side activity
  figures the funnel computes.
