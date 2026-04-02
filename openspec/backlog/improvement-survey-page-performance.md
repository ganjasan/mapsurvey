# Survey page load performance (Parallel)

**Type**: improvement
**Priority**: high
**Area**: frontend
**Epic**: survey-analytics
**Created**: 2026-04-02
**Depends on**: — (измерение эффекта зависит от [Survey event tracking](feature-survey-event-tracking.md))

## Description

Survey section page loads ~465KB of blocking resources (290KB JS + 175KB CSS) with zero async/defer. On mobile/slow connections this means 5-10 seconds of white screen, contributing to the 83% abandon rate on the Lyon transit survey. Optimize critical rendering path.

## Scope

- Add async/defer to non-critical JS (jQuery, Popper, Bootstrap JS)
- Lazy-load Leaflet Draw — only when section has geo-questions
- Font Awesome: replace with inline SVG for the 2-3 icons actually used, or load subset
- Google Fonts: preconnect + font-display:swap (partially done)
- Consider: defer map initialization until sidebar form is rendered first (perceived performance)
- Measure: add performance.now() timing to SurveyEvent for before/after comparison

## Current Load Profile

| Resource | Size | Blocking? |
|----------|------|-----------|
| jQuery 3.3.1 | 28KB | Yes |
| Popper.js | 20KB | Yes |
| Bootstrap JS | 50KB | Yes |
| Leaflet 1.4.0 | 130KB | Yes |
| Leaflet Draw | 60KB | Yes |
| Bootstrap CSS | 50KB | Yes |
| Leaflet CSS | 30KB | Yes |
| Font Awesome | 80KB | Yes |
| Leaflet Draw CSS | 15KB | Yes |
| **Total** | **~465KB** | **All blocking** |

## Notes

- Geolocation request can add 10s timeout on top of resource loading
- Directly impacts survey completion rate — performance IS a product feature here
- Measurement via SurveyEvent (Phase 2) will quantify the improvement
