# Project page: one public URL for the whole participation project

**Type**: feature
**Priority**: medium
**Area**: backend
**Epic**: pro-tier
**Tier**: **Pro**
**Created**: 2026-08-31

## Description

Maptionnaire charges for its "Communicate" layer — project pages with background text,
a process timeline, shared materials (plans, PDFs, video), embedded surveys and polls, and
auto-updating results, all under the client's branding. It is the only thing that
separates their base tier from the tier most customers buy
([gap analysis](../../docs/marketing/competitors/maptionnaire.md), §2.5).

We already have the hard half: the public results page (`/r/<slug>/`, live and frozen
modes, k-anonymity) and reference overlay layers. What is missing is the *hub* around a
survey: a page the municipality links from its own site, that says what the project is,
where it stands, how to take part, and what people have said so far.

## Scope Sketch

- `ProjectPage` (1:1 with a survey, or 1:N later): title, intro (rich text via the
  existing sanitiser), status/timeline steps with dates, materials list (links + uploaded
  PDFs/images via the S3 tiers), one or more surveys (open / closed state shown), and the
  results page embedded or linked.
- One template, sections toggled on/off — **not** a CMS. Drag-and-drop page building is
  the trap; the buyer wants a page that exists, not a page builder.
- Multilingual using the survey-content language picker; branding from `#90`.
- Lives under the custom domain when `#89` ships.

## Why Pro

This is representation of the project to a third party under the client's name — exactly
the Pro boundary in `pro-tier.md`. It is also the surface an interactive live poll
(Maptionnaire "Interactive live polls") would sit on; do not build polls separately.

## Related

`#130` auto-draft results page, `#131` embed widget, `#158` is the parent for `#21` live
results projection.
