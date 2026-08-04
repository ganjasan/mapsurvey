# White-label branding

**Type**: feature
**Priority**: high
**Area**: frontend
**Epic**: pro-tier
**Created**: 2026-07-29

## Description

Let a Pro workspace present surveys and public results pages as its own product: client
logo, brand colors and fonts, and removal of all Mapsurvey branding.

The buyer is a consultancy or an agency delivering participation for a municipality.
Their deliverable has to look like *their* work, or the client's own work — not like a
tool they subscribed to. This is one of the clearest and least contested reasons to pay
in the whole epic.

## Scope Sketch

- Workspace-level brand settings: logo, favicon, primary/accent colors, font choice,
  optional custom footer text and privacy/imprint links (German clients need an
  Impressum link that points at *them*).
- Applies to: public survey pages, password gate, thanks page, public results pages,
  exported PDFs/reports if any.
- Badge removal toggle, gated by entitlement — see
  [made-with-mapsurvey viral loop](feature-made-with-mapsurvey-viral-loop.md) (#75).
  Free keeps the badge; removing it is Pro.
- Live preview in the editor so the buyer can see the result before the call ends.

## Relationship to existing items

- [Survey visual customization (fonts, colors)](improvement-survey-visual-customization.md)
  (#42) is the respondent-facing styling slice — absorb it here rather than building
  twice, and treat it as the first shippable increment.
- [Custom domain](feature-custom-domain.md) (#89) is the same purchase motive at the URL
  level. Sell as one package: own domain + own brand + no third-party badge.

## Notes

- Guardrail: brand controls must not be able to break contrast or hide required legal
  links. Constrain the palette rather than shipping a free-form CSS field.
- Deliberate acquisition cost: every white-labelled survey is one that no longer
  advertises us. Accepted — the badge stays on the free tier, which is where the volume
  is anyway.
