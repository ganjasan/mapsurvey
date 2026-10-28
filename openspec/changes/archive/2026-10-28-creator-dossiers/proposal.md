## Why

Everything we know about the people using Mapsurvey lives in 125 hand-written
markdown dossiers on one laptop, under a gitignored `docs/` directory. Nothing
else has it: not the server, not a backup, not a second machine. If that disk
dies, the entire outreach history of the product goes with it.

It is also already drifting. Cohorts moved into the database on 2026-07-29; the
narrative that justifies each cohort did not. The dossiers still say "Tier 1A"
while the funnel dashboard computes activation live, so two records of the same
person disagree and there is no way to tell which is current.

And the format resists every next step. A dossier cannot be queried ("which
consultancies did we last contact more than 60 days ago?"), cannot be handed to
a second person, and cannot be exported into a CRM without a human reading 125
files and retyping them.

This change moves creator knowledge into the database as a small, deliberately
CRM-shaped record, so it survives the laptop, stays next to the cohort it
explains, and can be exported when a real CRM arrives.

## What Changes

- New `CreatorProfile`, one per user: the structured facts we repeatedly look
  up — organisation, role, country, LinkedIn, website, how they found us — plus
  a short markdown summary. These map one-to-one onto the Company/Contact fields
  of any CRM.
- New `CreatorNote`, many per user: an append-only timeline of what we learned
  and did, each with a date, an author, a kind (`research`, `email`, `call`,
  `signal`) and a markdown body. Notes are never edited in place by tooling, so
  the history of a relationship stays legible. These map onto CRM Activities.
- An importer that reads the existing `docs/marketing/user-outreach/` tree:
  header fields into the structured columns, the dossier body into a first
  `research` note, and each `correspondence/*.md` into a dated `email` note.
  Dry run by default, idempotent, and it never modifies the source files.
- Staff UI in the Django admin: the profile and the note timeline appear on the
  user page, next to cohorts, so one screen answers "who is this".
- A CSV export of profiles and notes, so migrating to a CRM is a file handover
  rather than a re-typing project.

## Capabilities

### New Capabilities

- **creator-dossiers**: store structured facts and an append-only note timeline
  about each registered creator, import the existing markdown dossiers into it,
  and export the result for a CRM.

## Non-Goals

- Not a CRM. No deal stages, no pipeline, no reminders, no email sending. The
  goal is durable storage with a clean exit, not a product to live in.
- No sync back to the markdown files. After the import, the database is the
  source of truth; the files stay as a frozen historical record.
- Nothing user-facing. Profiles and notes are staff-only and never shown to the
  person they describe.

## Privacy

These are personal notes about identifiable people, held on infrastructure in
the US (Render, Oregon). Two consequences that shape the design rather than
merely warning about it:

- A GDPR subject access request obliges us to hand over everything we hold about
  that person, including these notes verbatim. The CSV export doubles as the
  mechanism for answering such a request, and the admin makes deletion a single
  action.
- Notes must be written as if the subject will read them, because they may.
  Judgements about a person's budget or competence belong in the note only when
  we would defend them to their face.
