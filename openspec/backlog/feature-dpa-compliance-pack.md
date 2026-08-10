# DPA / AVV compliance pack

**Type**: feature
**Priority**: very high
**Area**: general
**Epic**: pro-tier
**Created**: 2026-07-29

## Description

The paperwork half of the geo-zone offer. Choosing an EU region answers *where the server
is*; this answers *who can legally reach the data* — which is the question a German
Datenschutzbeauftragte actually asks, and the one that decides whether a deal starts at
all.

We are not selling geography. We are selling the ability to answer the client's data
protection officer **in writing**.

## Scope Sketch

- **AVV / DPA under Art. 28 GDPR**, signable, in German and English. A municipality is
  the controller, a consultancy like ThINK is the processor, we are the subprocessor —
  the document must model that chain correctly.
- **Subprocessor list** (hosting provider, email, error tracking, CDN) with change
  notification procedure.
- **Standard Contractual Clauses** plus an honest description of third-country access:
  a Kyrgyzstan-based operator administering EU-hosted data is a transfer at the access
  level. Describe it, do not omit it — an omission found later kills the account.
- **Access register**: who holds administrative access, from where, under what controls.
- **Incident notification** commitment and timeline.
- **TOM description** (technische und organisatorische Maßnahmen) — standard annex to an
  AVV; German buyers expect it and its absence reads as amateurism.
- Self-serve download + countersignature flow in the workspace, so procurement does not
  have to email us and wait.

## Why "we are GDPR compliant" is not enough

- Data residency ≠ data sovereignty: an EU datacentre run by a US company is still
  CLOUD Act exposed. Canadian public bodies (BC FIPPA since Bill 22, 2021-11-25) now
  require a jurisdictional PIA that addresses exactly this.
- EU-US Data Privacy Framework is valid but not a foundation to build on: the General
  Court dismissed the Latombe challenge on 2025-09-03, an appeal is pending at the CJEU
  (C-703/25 P, filed 2025-10-31), and the PCLOB has lacked quorum since January 2025.
  Selling "we are in the US but DPF covers it" is signing up for Schrems III.
- German public sector: BDSG adds requirements beyond GDPR, and many agencies and their
  contractors are expected to keep data on German territory rather than merely in the EU.
  BSI C5 shows up as a procurement criterion.

## Dependencies / Related

- [EU / multi-region hosting](feature-eu-data-hosting-option.md) (#35) — the technical half
- [Frankfurt server migration](improvement-frankfurt-server-migration.md) (#11)
- [Grant reporting pack](feature-grant-reporting-pack.md) (#94)
- Existing `/trust/` page (`2026-04-02-trust-page`) is the public-facing entry point
- **2026-08-10 — partially shipped.** An English Art. 28 DPA exists at `survey/assets/dpa/mapsurvey-dpa.pdf`, linked from `survey/templates/trust.html:142`. Missing for German buyers: the German AVV, SCC / third-country access disclosure, the access register, sub-processor change notification, and a self-serve countersignature flow.
