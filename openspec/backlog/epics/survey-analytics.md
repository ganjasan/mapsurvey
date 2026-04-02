# Survey Analytics & Optimization

**Created**: 2026-04-02

## Vision

Give survey creators a GTM-like analytics experience: see the funnel, understand where respondents drop off, know where traffic comes from, and run A/B tests to optimize response quality.

## Phases

### Phase 1: MVP Dashboard
Analytics page with overview stats, daily chart, response map, and per-question distributions. Built from existing data, no migrations.

### Phase 2: Event Tracking & Referrer
SurveyEvent model for granular funnel tracking (section-level drop-off), referrer capture (HTTP Referer), device/UA info, and page load performance metrics.

### Phase 3: UTM & Link Generator
UTM parameter parsing, trackable link generator UI with QR codes, per-source breakdown in dashboard.

### Phase 4: A/B Testing
Version-based split testing with configurable traffic percentage, variant comparison dashboard, statistical significance.

### Parallel: Survey Page Performance
async/defer JS, lazy-load Leaflet Draw, Font Awesome subset — reduce ~465KB blocking resources.

## Real-World Driver

Lyon transit survey (bisqunours): 562 sessions, 98 completed, 83% abandon rate. Creator has no visibility into these metrics. Co-design partner for Phase 1.

## Related Backlog Items

- feature-survey-analytics-dashboard.md (Phase 1)
- feature-survey-event-tracking.md (Phase 2)
- feature-referrer-tracking.md (Phase 2)
- feature-utm-link-generator.md (Phase 3)
- feature-ab-testing.md (Phase 4)
- improvement-survey-page-performance.md (Parallel)
- feature-number-field-min-max-validation.md (related)
- feature-results-dashboard.md (related — response data viz)
- feature-public-results-map.md (related)
