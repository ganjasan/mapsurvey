# Survey analytics dashboard (Phase 1 MVP)

**Type**: feature
**Priority**: high
**Area**: frontend
**Epic**: survey-analytics
**Created**: 2026-04-02
**Depends on**: —

## Description

Analytics page at `/surveys/<uuid>/analytics/` accessible only to survey creator. Shows overview stats (sessions, completed, completion rate), daily response chart, response map with all geo-points, and per-question statistics (choice distributions, number avg/median/range, text answer list). Built entirely from existing data — no new models or migrations needed.

## Scope

- Overview card: total sessions, completed count, completion rate with visual bar
- Daily response chart (CSS bars or Chart.js)
- Response map: all geo-point answers on a single Leaflet map
- Per-question stats: bar charts for choice, stats for number, list for text
- Auth: only survey creator can access

## Notes

- Real case: Lyon transit survey (bisqunours) — 562 sessions, 98 completed, 83% abandon rate. Creator cannot see this
- bisqunours will be co-design partner for this feature
- No migrations — reads existing SurveySession + Answer data
- Related to `feature-results-dashboard.md` (response data viz) but distinct — this is survey performance analytics
