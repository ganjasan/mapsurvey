# Billing & invoicing for Pro (project-based)

**Type**: feature
**Priority**: very high
**Area**: backend
**Epic**: pro-tier
**Created**: 2026-07-29

## Description

The ability to take money in a form an institutional buyer can pay. Not a card form —
a **proper invoice against a purchase order or a grant budget line**, because that is how
municipalities and consultancies actually pay.

The unit is a project, not a seat: a grant funds a participation project with a start and
an end, and the invoice has to match the line item in the application.

## Scope Sketch

- Quote/offer generation (Angebot) with scope, term, and price — needed before a buyer
  can even put us in a budget.
- Invoice generation with correct VAT handling; EU reverse-charge for B2B customers,
  VAT ID capture and validation.
- Project-term licences (fixed period tied to the participation project) alongside any
  recurring option.
- Purchase-order reference field — public buyers cannot pay an invoice without one.
- Card payment as a convenience path for smaller/self-serve buyers, but never the only
  path.
- Receipts and documentation the customer can put into a Verwendungsnachweis — see
  [grant reporting pack](feature-grant-reporting-pack.md) (#94).

## Blocking structural question

Invoicing a subsidised German project from a **Kyrgyzstan entity** creates friction the
product cannot fix:

- reverse-charge treatment and whether the buyer's accounting accepts a non-EU supplier
- the grant recipient's obligation to justify supplier choice to the funder
- programme-level restrictions on procurement outside the EU in some funding lines
- payment rails: what a German municipality's finance department will actually transfer to

**An EU legal entity may be the entry ticket rather than an optimisation.** This decision
gates the whole Pro tier and is not a development task — it needs deciding before pricing
is published.

## Notes

- Anchor pricing against Maptionnaire / Citizen Space (£10.5K–100K per instance per year)
  and Open Point ($15–40K per deal), never against zero.
- Quote alongside the funding rate where it applies: under the Kommunalrichtlinie,
  Akteursbeteiligung is funded at 70% (90% in coal regions), so state both the price and
  the share the municipality actually carries.
- Ship "Pro is visible" before "Pro is billable" — for sales calls, a coherent tier with
  real content matters more than working checkout.
