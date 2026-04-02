# A/B testing via survey versions (Phase 4)

**Type**: feature
**Priority**: medium
**Area**: backend
**Epic**: survey-analytics
**Created**: 2026-04-02
**Depends on**: [Survey analytics dashboard](feature-survey-analytics-dashboard.md), [Survey event tracking](feature-survey-event-tracking.md)

## Description

Allow survey creators to run split tests between two published versions of a survey. Creator publishes a new version as an "experiment" instead of replacing the current one. Traffic is split by configurable percentage (default 50/50). Dashboard shows per-variant completion rate with statistical significance.

## Scope

- New model: SurveyExperiment (canonical survey FK, variant_a FK, variant_b FK, split_percent int, status, started_at, ended_at)
- Survey entry view: if active experiment, randomly assign variant based on split_percent, persist assignment in cookie/session
- Editor UI: "Run experiment" option when publishing a new version (instead of replace)
- Dashboard: side-by-side variant comparison (sessions, CR, per-question stats)
- Statistical significance calculation (chi-squared or z-test for proportions)
- End experiment: pick winner, close loser

## Notes

- Builds on existing versioning system (canonical_survey, version_number)
- Depends on Phase 1-2 (dashboard + event tracking) for meaningful comparison
- Cookie-based assignment ensures returning respondents see same variant
- Consider: should assignment be deterministic (hash of session ID) for reproducibility?
