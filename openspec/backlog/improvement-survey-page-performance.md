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

## Measured on production, 2026-08-17

SurveyEvent `page_load` data now exists, so the April estimate above ("5-10 seconds on
mobile") can be replaced with numbers. Survey 440 (*Mapa colaborativo LGBT+ em Belo
Horizonte*, 29 sessions, all traffic 2026-08-10/11) — median `load_ms` by device, all
sections except the first (the first has no map):

| Device | Loads | Median | p90 |
|--------|-------|--------|-----|
| desktop | 44 | 0.9 s | 41 s |
| mobile | 16 | **36.5 s** | 50 s |

Same survey, median by section: S1 (no map) 0.8 s, S2 6.5 s, S3 16.6 s, S4 22 s, S5 11.5 s.
The map is the whole difference.

The estimate was low by roughly 4x, and it is a *mobile* problem specifically — desktop is
fine. Completion on that survey: 5/20 desktop vs 1/9 mobile, with mobile at 31% of sessions.

Cross-survey check over the last 30 days (median `load_ms`, non-first sections): surveys
373/383/441 sit at 320–490 ms, while 379 is at 56 s, 396 at 35 s, 438 at 30 s. So this is
not uniform — some configurations are fine and some are catastrophic, which suggests a
per-survey trigger on top of the fixed 465KB bundle.

Candidate trigger, unverified: survey 440 enables three basemaps (`streets`, `satellite`,
`topo`) where most surveys enable one. Worth checking whether all enabled basemaps get their
tiles fetched at init rather than on switch.

**Reproduce before changing anything**: PR preview, throttled to 4G, a section with three
basemaps enabled, read the network waterfall. Do not optimize from this table alone —
`load_ms` measures to the `load` event, so a backgrounded tab inflates the tail (though not
a median of 36 s).

## Notes

- Geolocation request can add 10s timeout on top of resource loading
- Directly impacts survey completion rate — performance IS a product feature here
- Measurement via SurveyEvent (Phase 2) will quantify the improvement
