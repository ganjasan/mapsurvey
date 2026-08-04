# Survey visual customization (fonts, colors)

**Type**: improvement
**Priority**: medium
**Area**: frontend
**Epic**: pro-tier
**Tier**: **Pro**
**Created**: 2026-03-26
**Updated**: 2026-08-04 — added question/section spacing and separators to scope
**Updated**: 2026-07-29 — folded into white-label branding; priority raised from low

## Description

Allow survey creators to customize visual appearance: background color, font color, font family, text size. Enables institutional branding and visual consistency with organization's identity.

Also in scope, and cheaper than the branding work: the default respondent-facing spacing itself.
The gap between a question and its answer options is tight enough to read as one block, and the
gap between a section subheading and the first question is tighter still. An optional separator
rule between questions would carry most of the benefit on its own.

## Notes

- Source: Manuel Frost (manu04) — nice to have
- **2026-07-29**: this is the respondent-facing styling slice of
  [white-label branding](feature-white-label-branding.md) (#90) — build it there rather than
  twice, and treat it as the first shippable increment of that feature. Reclassified from
  "nice to have" to a paid capability: institutional branding is exactly what a consultancy
  delivering to a municipality pays for. See [epics/pro-tier.md](epics/pro-tier.md).
- Guardrail: constrain the palette so brand settings cannot break contrast or hide required
  legal links — no free-form CSS field.
- **2026-08-04**: Manuel Frost repeated the request, specifically asking for a separator line
  between questions and more air around the subheading. He also asked to "place a short text
  without an answer option" — that already exists as the `html` question type
  (`survey/forms.py:219`) and he did not find it. Treat the discoverability of `html` as part of
  this item: the type name says nothing about what it is for. See
  [Sub-question Discoverability Testing](idea-subquestion-discoverability-testing.md) (#61) for
  the same failure mode on another feature.
- The default spacing fix is not gated on Pro — it improves every survey and should ship
  independently of the branding controls.
