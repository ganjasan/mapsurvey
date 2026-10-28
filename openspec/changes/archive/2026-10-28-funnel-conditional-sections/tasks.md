## 1. Funnel computation

- [x] 1.1 In `survey/analytics.py`, add a helper that resolves each section's rule via
      `survey.visibility._rule_verdict` (valid → controller question + matchable codes; broken →
      reason) and reads eligible session ids from `Answer` (`question__code`, session scope,
      `selected_choices` ∩ codes).
- [x] 1.2 Rework `get_funnel()`: baseline = last unconditional step; per step emit `conditional`,
      `rule_label` (via `describe_rule`), `rule_broken`, `rule_reason`, `eligible`, `skipped`,
      `skipped_pct`, `eligible_pct`, `baseline_step`; `dropped`/`dropped_pct` per design D1/D2.
- [x] 1.3 Tests in `PerformanceAnalyticsServiceTest` (GIVEN/WHEN/THEN): skipped-not-dropped,
      loss-inside-branch, broken-rule-fails-open, successor-not-inflated, real-loss-after-branch.

## 2. Rendering

- [x] 2.1 `analytics_performance.html`: `is-conditional` class, branch badge (`fa-code-branch`,
      editor colours) with truncated label + full `title`, `.perf-funnel-skipped` band, "skipped by
      rule" line, "dropped … of eligible" line, "since step N" caption, warning badge for broken
      rules, legend under the chart.
- [x] 2.2 `_analytics_styles.html`: conditional frame, band, badge, legend swatches; phone media
      query renders the band on the horizontal bar (`--reached`/`--skipped`).
- [x] 2.3 Dashboard render tests: conditional markup, successor caption, broken-rule badge.
- [x] 2.4 Run the template-comment guard test right after editing the partial.

## 3. Localisation and wrap-up

- [x] 3.1 Add the new strings to every catalog in `survey/locale/*/LC_MESSAGES/django.po` and
      compile (`compilemessages`).
- [x] 3.2 Run `./run_tests.sh survey` once before and once after; summarise the delta.
- [x] 3.3 Verify against the mockup in a browser (desktop + 360px) on a seeded survey with a
      conditional section.
