# Bound where a respondent may draw — study area and exclusion zones

**Type**: feature
**Priority**: high
**Area**: frontend
**Created**: 2026-08-26

## Description

The creator marks the area a respondent may place geometry in, and optionally areas they may
not. PARTIMAP draws the permitted area as a dashed boundary and the exclusions as grey
polygons carrying a minus sign, both visible before the respondent touches anything
([screenshot](../../docs/marketing/competitors/partimap/10-draw-with-bounds.jpg)).

Two separate jobs, and the visual one matters more than the enforcement one: a respondent who
can see the study area does not wander out of it. Rejection after the fact is the fallback,
not the feature.

## What it needs

- Boundary geometry on the survey or section — reuse the overlay layer machinery from FD-1
  rather than adding a second upload path, with a flag marking a layer as "the study area".
- Rendering that reads as a boundary and not as content: dashed outline, dimmed exterior.
- **Soft first.** This was already decided once, in
  [FD-14](feature-answer-driven-map-context.md): a volunteer standing one street over the
  boundary must not be blocked from recording a real observation. Show the area, warn on the
  way out, still accept the point.
- Hard enforcement as an explicit per-question setting for the cases that need it —
  `validation_settings` already exists for this.
- Server-side check whenever hard mode is on. Bounds enforced only in JavaScript are not
  enforced; see [answers never validated server-side](bug-answers-never-validated-server-side.md).
- Lines and polygons need a rule of their own — is a route that leaves the area and comes back
  inside or outside? Simplest defensible answer: judge by whether it intersects the area at all
  in soft mode, and require full containment in hard mode.

## Notes

- Cheap relative to its effect on data quality, and data quality is invisible to us until it
  is bad: per [[lesson-authors-workaround-silently]] authors work around gaps in silence, so
  nobody will report "my respondents keep marking the wrong town".
- Overlaps with [FD-14](feature-answer-driven-map-context.md), which scopes the map from a
  previous answer. That item switches *which* area; this one defines what an area means for
  drawing. FD-14 depends on this being settled.
- Epic: field-data-collection
