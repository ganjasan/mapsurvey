# Survey event tracking (Phase 2)

**Type**: feature
**Priority**: high
**Area**: backend
**Epic**: survey-analytics
**Created**: 2026-04-02
**Depends on**: —

## Description

SurveyEvent model for granular tracking of respondent behavior: session start, section view, section submit, survey complete. Enables section-level funnel analysis ("Section 2 loses 40% of respondents") and time-spent metrics. Also captures device info (user agent) and page load performance (via JS `performance.now()`).

## Scope

- New model: SurveyEvent (session FK, event_type enum, section FK nullable, question FK nullable, timestamp, metadata JSONField)
- Event types: session_start, section_view, section_submit, survey_complete
- Capture in views: emit events at key points in survey flow
- JS snippet: send page_load_time as event metadata
- Device/UA: capture from request headers on session_start
- Dashboard integration: funnel visualization, time-on-section, device breakdown

## Notes

- Event log approach (vs SectionView model) — more flexible, extensible for future event types
- Metadata JSONField allows storing arbitrary context without schema changes
- Consider write performance at scale — batch inserts or async writes if needed
