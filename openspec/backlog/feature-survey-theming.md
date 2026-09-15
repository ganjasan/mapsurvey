# Survey theming — let the creator style their survey a little

**Type**: feature
**Priority**: medium
**Area**: frontend
**Created**: 2026-08-23

## Description

A small, curated set of appearance controls per survey: accent color (buttons, links,
selection states), page background tint for form-layout sections, optional header/cover
image on the welcome section, maybe a font pairing choice. Applied to respondent surfaces
only. "A little" is the spec: a color and a cover, not a CSS editor — Google Forms proves
that a handful of knobs covers almost everyone.

Prompted by the mapless-sections work (2026-08-23): once a survey renders as a classic
form card, its look IS the organisation's public face — Olney would reasonably want their
squirrel-brand maroon rather than our indigo.

## Notes

- Storage: extend the existing `SurveyHeader.style_settings` JSON (already holds
  `rating_display_style` and has a sanitizing `_clean_style_settings` on import) — no new
  model. Render as CSS custom properties on the respondent page.
- Validate hard: colors are hex-checked, images go through the existing upload path;
  nothing here may accept raw CSS or HTML.
- Boundary with [white-label branding](feature-white-label-branding.md) (#90, Pro):
  theming = your colors on your survey (Free is fine); white-label = removing OUR brand
  (stays Pro). Keep the two knobs in the same settings panel but priced separately.
- Cover image on the welcome page pairs with #144/#145 (mapless sections).
