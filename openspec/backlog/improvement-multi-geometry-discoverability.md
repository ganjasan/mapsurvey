# One geo question already accepts many features, and nobody knows it

**Type**: improvement
**Priority**: very high
**Area**: frontend
**Created**: 2026-08-05

## Description

A geo question accepts **any number of geometries**, and each drawn feature carries its own
answers to that question's sub-questions. This is the repeatable-group mechanism the product
needs, and it has worked for a long time. Nothing in the editor or in the respondent view says
so, so authors assume one question means one feature and build around the assumption.

## The case that surfaced it

`angele.trolliet@vaucluse.chambagri.fr`, Chambre d'agriculture de Vaucluse, 2026-08-04.
A farm survey for the Ansouis protected agricultural zone (ZAP), a real prefecture-level
procedure. She built:

```
Localisation des parcelles/ îlots parcellaires n°1    polygon
    ├── Types de production/ activité
    ├── Labels/ certification
    └── Irrigation
Localisation des parcelles/ îlots parcellaires n°2    polygon
    ├── ... the same three sub-questions
... twelve times ...
```

**106 questions where 11 would do.** She then wrote the workaround into the respondent
instructions herself:

> «Si votre exploitation comporte plusieurs secteurs distincts, vous pouvez les dessiner dans
> les emplacements prévus à cet effet: "îlots parcellaires n°1, n°2, etc..."»

Consequences she absorbed without complaining:

- A farm with more than twelve parcels cannot answer accurately. The ceiling is invisible to
  the respondent until they hit it.
- Copying the block twelve times by hand dropped the `Irrigation` sub-question from block
  n°10. One parcel per response will silently have a missing attribute.
- The GeoJSON export comes out as twelve one-feature layers instead of one parcel layer with
  an attribute, which is the opposite of what a GIS workflow wants.

She had in fact already drawn two polygons on a single question during testing, so the
capability was demonstrated to her by accident and still not noticed.

## Why this is worth a "very high"

This is not a missing feature. It is a **built feature that fails to be found**, by an
institutional user with a funded, deadline-bound project, who was motivated enough to spend
an afternoon on it. The cost of the miss lands on data quality for every respondent, and we
only saw it because the account happened to be reviewed before the survey went to the field.

Every other author who assumed the same thing built a smaller survey and told us nothing.

## Proposed fix

**Editor, on any geo question**: state the behaviour where the author is looking. Something as
plain as "Respondents can add as many features as they need. Each one gets its own answers to
the sub-questions below." next to the sub-question list.

**Respondent view**: after the first feature is drawn and its popup is filled, the map should
invite the next one rather than sit there. A visible "add another" affordance, and a count of
what has been drawn so far.

**Editor preview**: the author needs to see the multi-feature behaviour once, in preview,
before the survey ships. Seeing it is worth more than reading it.

## Longer-term

If a survey genuinely needs a bounded repeat ("up to 3 sites"), that is a per-question
`max_features` setting, not twelve copies of a block. Worth considering only after
discoverability is fixed; the ceiling was never the thing people wanted.

## Notes

- A corrected version of her survey (11 questions, one parcel question) was built and verified
  by real import into a local DB: `docs/marketing/user-outreach/angele_trolliet/enquete-agricole-zap-ansouis-simplifiee.zip`.
- Precedent that the mechanism works: the Berlin RuE survey (`manu04`) carries 30
  sub-question answers per drawn feature, several features per session.
- Related: [Sub-question popup is too narrow](bug-subquestion-popup-too-narrow.md) — the same
  sub-question mechanism, failing at the next step. The more features a respondent draws, the
  more times they meet that popup.
