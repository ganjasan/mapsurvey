# Hosting geo-zone selection (EU / US)

**Type**: feature
**Priority**: very high
**Area**: infra
**Epic**: pro-tier
**Created**: 2026-04-05
**Updated**: 2026-07-29 — reframed from "EU option" to a Pro workspace parameter; priority raised

## Description

Let a workspace choose the geographic zone its data lives in, and hold it there. Pro
feature — this is the single most blocking requirement in institutional deals, and the
first question a German or French public-sector buyer asks.

Originally scoped after KoboToolbox's Global/EU server choice (they offer Global + EU
Ireland at signup). Reframed 2026-07-29: this is not a signup preference, it is the entry
condition to the Pro tier's target market.

## Scope Sketch

- Zone chosen at workspace creation: **EU (Frankfurt)** and **US**, no migration between
  them in v1 (cross-zone migration is a separate, much harder problem — do not promise it).
- Zone is visible in the workspace UI and stated in the DPA, because the customer has to
  quote it to their own data protection officer.
- All personal data paths must respect it: database, uploaded images, backups, logs,
  error tracking, email.
- Add further zones only against a concrete deal (UK, CA, AU are the plausible next ones).

## Recommended shape

Two zones from the start (EU + US), selectable at workspace creation, no cross-zone
migration. Rationale: a one-way move to the EU would close the US public sector, which
requires the opposite (FedRAMP / StateRAMP / CJIS expect US storage). The two markets pull
in different directions, so single-zone is not a stable answer.

## Who actually requires this (research 2026-07-29)

- **Germany — primary market.** GDPR itself does not mandate EU hosting, but BDSG is
  stricter for the public sector, and many agencies and their contractors are expected to
  keep data on German territory, not merely in the EU. BSI C5 appears as a procurement
  criterion. In practice the requirement arrives as municipal policy and via the
  Datenschutzbeauftragte — which is harder than the law, because it is not negotiable.
- **France — strictest in Europe.** Sensitive public-administration data must by law sit
  on a SecNumCloud-qualified cloud. Qualification requires localisation of *all* data
  (personal and non-personal) in the EU, support performed by EU-based staff, and caps on
  non-EU ownership (<25% single, <39% combined) with no veto or board control —
  effectively a local joint venture. French public sector is closed to us for sensitive
  categories; whether ordinary participation data counts is decided per tender.
- **Canada.** BC FIPPA's hard in-Canada requirement was repealed by Bill 22 effective
  2021-11-25, but public bodies must now run a jurisdictional PIA addressing CLOUD Act
  exposure. Not a ban — an extra document someone has to write, which is deal friction.
- **Australia.** Localisation for specific categories (health, financial); separate
  government cloud schemes.
- **United States public sector.** Pulls the other way — FedRAMP / StateRAMP / CJIS
  expect US storage. Our current Oregon hosting is an asset there.

## The distinction that matters

**Data residency ≠ data sovereignty.** Where the server sits is technical; who can
legally compel the data is jurisdictional. An EU datacentre operated by a US company is
still CLOUD Act exposed — which is exactly what Canada now requires be analysed and what
SecNumCloud forbids outright. Moving to Frankfurt solves half the problem; the other half
is our own corporate structure and who holds administrative access, and it is answered on
paper — see [DPA / AVV compliance pack](feature-dpa-compliance-pack.md) (#88).

Do not build the pitch on the EU-US Data Privacy Framework: valid today (General Court
dismissed the Latombe challenge 2025-09-03) but under appeal at the CJEU (C-703/25 P,
filed 2025-10-31), with the PCLOB out of quorum since January 2025.

## Cartographic restrictions — specific to a geo product

Beyond privacy, some jurisdictions restrict map data itself. South Korea's 2014 Act on
the Establishment and Management of Spatial Data bars export of detailed digital maps
(finer than 1:25,000) without government approval — Google only received conditional
approval in February 2026. China, Iran and Syria apply comparable rules. For those
markets an EU zone does not help: it needs in-country hosting and a local basemap. Not a
priority, but it means "add a zone" is not always the answer. India was not verified —
check separately if a lead appears.

## Dependencies / Related

- [Frankfurt server migration](improvement-frankfurt-server-migration.md) (#11) — the infra move
- [DPA / AVV compliance pack](feature-dpa-compliance-pack.md) (#88) — the contractual half
- [Plans & entitlements](feature-workspace-plans-entitlements.md) (#87) — the gate
- Source of the original request: Manuel Frost (Berlin Senate IT security); ThINK Jena is
  the current live driver

## Confirmed as a blocker on a live call (2026-07-31)

ThINK Jena (Marcus Wildner + Heiko Griebsch) stated the requirement unprompted and
specifically: **a server in Frankfurt, in Germany.** Not "in the EU" — in Germany. This
matches the research above: the requirement arrives as institutional policy, and policy
is not negotiable the way law sometimes is.

They are a consultancy working *for* municipalities, so the requirement is inherited from
their clients, which makes it worse for us, not better: they cannot waive it, and they
will be asked to prove it in every tender they enter. As it stands we do not meet it, and
"we may come back in a few months" is the polite form of that.

Consequence for sequencing: for a consultancy the smallest credible answer may be a
**dedicated instance on German infrastructure for one project**, not a general EU zone.
That is a services-shaped answer, deliverable per deal, and it would let us learn what
the DPA actually has to say before building the multi-zone product. See
[DPA / AVV compliance pack](feature-dpa-compliance-pack.md) (#88).
