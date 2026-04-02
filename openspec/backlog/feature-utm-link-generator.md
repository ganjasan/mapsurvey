# UTM parameters & link generator (Phase 3)

**Type**: feature
**Priority**: medium
**Area**: frontend
**Epic**: survey-analytics
**Created**: 2026-04-02
**Depends on**: [Survey event tracking](feature-survey-event-tracking.md)

## Description

Parse UTM query parameters (utm_source, utm_medium, utm_campaign) from survey URLs and store them in SurveyEvent. Provide a UI in the editor for generating trackable links with pre-filled UTM fields and QR code generation. Show per-source breakdown in analytics dashboard.

## Scope

- Parse utm_source, utm_medium, utm_campaign from query string on survey entry
- Store in SurveyEvent metadata (or dedicated fields)
- Editor UI: "Share & Track" panel with fields for source/medium/campaign
- Generate copyable URLs with UTM params
- QR code generation (via JS library or server-side)
- Dashboard: per-source/campaign breakdown table and chart

## Notes

- Depends on SurveyEvent model (Phase 2)
- UTM provides precise attribution vs referrer (Phase 2) which is automatic but less specific
- Example: `https://mapsurvey.org/surveys/<uuid>/?utm_source=instagram&utm_campaign=lyon_transit`
