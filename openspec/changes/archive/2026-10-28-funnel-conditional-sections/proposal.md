## Why

The Section Funnel on the Performance pane treats every section as a step everyone walks through.
A section behind a visibility rule is shown only to respondents who picked a given option, so the
funnel reports the people the rule *skipped* as "dropped" (a real survey shows "7 dropped (22%)"
and "21 dropped (66%)" on branches nobody abandoned) and the next section, reached by everyone,
looks as if it gained respondents out of nowhere. A creator reading this either distrusts the
whole pane or "fixes" a branch that works exactly as designed.

## What Changes

- The funnel distinguishes three outcomes per conditional section: **reached**, **skipped by
  rule** (the controlling answer did not match — never shown the section) and **dropped**
  (eligible but never viewed it). Drop rate on a conditional section is relative to the eligible
  respondents, not to everyone.
- A section that follows a branch compares itself with the last *unconditional* step, so a
  conditional step can no longer make its successor look like it gained respondents.
- Conditional steps are legible in the chart: the same branch badge the editor structure pane
  uses ("Shown when <question> = <options>"), a distinct bar frame, and a light band in the bar for
  the skipped share; a legend explains the three fills.
- A section whose rule is broken (fail-open, shown to everyone) renders as an unconditional step
  with the editor's warning badge.
- Existing `views`/`submits`/`drop_rate` payload keys and the small-sample notice stay as they are.

## Capabilities

### New Capabilities
- (none)

### Modified Capabilities
- `survey-performance-analytics`: the section funnel requirement gains conditional-section
  semantics (skipped vs dropped, eligible-based rate, baseline = last unconditional step) and the
  step chart gains the conditional rendering. The capability's current requirements live in the
  still-unarchived change `performance-section-funnel`; this change adds new requirements rather
  than MODIFIED blocks so archiving does not depend on that change's order.

## Impact

- `survey/analytics.py` — `PerformanceAnalyticsService.get_funnel()` gains eligibility
  computation from `Answer.selected_choices` via the visibility engine's rule verdict.
- `survey/visibility.py` — reuse `describe_rule` for the badge label; no engine change.
- `survey/templates/editor/partials/analytics_performance.html` and
  `_analytics_styles.html` — conditional step markup, skipped band, legend, phone layout.
- `survey/tests.py` — `PerformanceAnalyticsServiceTest` and the dashboard render test.
- Locale catalogs (`survey/locale/*/django.po`) — new strings for the badge, "skipped by rule",
  "of eligible", "since step N" and the legend.
- No migrations, no new settings.
