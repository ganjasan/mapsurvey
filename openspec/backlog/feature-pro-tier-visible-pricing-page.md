# Pro tier visible: pricing page, plan badge, copy rewrite

**Type**: feature
**Priority**: **very high**
**Area**: frontend
**Epic**: pro-tier
**Tier**: — (the surface that *sells* Pro)
**Created**: 2026-08-31

## Description

Nothing on mapsurvey.org today tells a buyer that a paid tier exists, what it contains, or
what it costs. `for_consultants.html` still promises "keep the tooling cost at zero";
`/services/` sells hours, not a product. Every institutional lead (ThINK, Flagship, Olney)
has had to be told the model by email, and Olney got a number ($49/mo) that appears nowhere
public. The first revenue step is not billing code — it is a page a buyer can forward to
their finance department.

Maptionnaire's `/subscription` is the reference shape (see
[`docs/marketing/competitors/maptionnaire.md`](../../docs/marketing/competitors/maptionnaire.md)):
tracks above tiers, a 61-row plain-language feature table with expandable descriptions, and
explicit "no per-survey, per-respondent or per-seat metering" language.

## Scope Sketch

- `/pricing/` with two offers, mirroring the buyer's unit of purchase:
  **Project licence** (fixed term, one participation project, all Pro features, no renewal)
  and **Workspace** (annual, unlimited projects). Free is described in one paragraph and
  linked from the footer, not shown as a column — Free is a channel, not a plan
  ([pro-tier.md](epics/pro-tier.md)).
- Feature table Free vs Pro from the split already decided in `pro-tier.md`; rows phrased
  in the buyer's words ("read-only access for your client", "hosted in the EU").
- A published anchor price with the co-funding line where it applies ("of which the
  municipality carries 30% under the Kommunalrichtlinie"). Anchor against
  Maptionnaire / Citizen Space / Open Point, never against zero.
- Plan badge in the editor header (Free / Pro / Pilot) so the tier is *visible* inside the
  product before it is billable — reads from `#87` when that ships, hard-coded "Free" before.
- Rewrite `for_consultants.html`, `/services/` and the trust page so no surface still says
  "zero cost" to a payer.
- CTA = request a quote / start a project (mailto + form), UTM-tagged into the funnel.

## Dependencies

- Price and the EU-entity question in [#93](feature-billing-invoicing.md) must be *decided*,
  not built, before this ships — the page can say "from X €/project" without a checkout.
- [#87](feature-workspace-plans-entitlements.md) for the live badge; not a blocker.

## Notes

- Ship "Pro is visible" before "Pro is billable" — rollout rule from `pro-tier.md`.
- Olney was quoted $49/mo per organisation plus a per-project alternative; whatever lands
  here must not contradict that quote.
