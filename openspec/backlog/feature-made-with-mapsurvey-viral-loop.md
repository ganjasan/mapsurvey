# "Made with Mapsurvey" viral loop on public pages

**Type**: feature
**Priority**: high
**Area**: frontend
**Epic**: growth
**Created**: 2026-06-10

## Description

Turn the platform's highest-volume asset — survey responses — into an acquisition surface. Today thousands of people open and complete public surveys but never see a reason or a path to create their own, so this traffic converts to zero registrations. Add a tasteful, non-intrusive "Made with Mapsurvey — create your own free geo-survey" element to the public-facing pages:

- public survey page (footer/badge while answering)
- thanks page (after submission — highest-intent moment)
- **public results page** (`/r/<slug>/`) — the highest-value placement: anyone viewing aggregated results is already "thinking like a creator"

## Evidence (from 2026-06-10 analysis)

- Response volume is abundant (thousands of sessions) but leaks ~0 attributable signups — e.g. the Lyon transit survey drew 658 responses with no registration bump.
- This feature directly attacks that leak by giving respondents/results-viewers a path. Even a 0.5% conversion would exceed current organic signup volume, and the loop compounds.

## Scope

- Configurable badge/CTA component, shown on public survey + thanks + results pages.
- Creator-side toggle to hide it (respect surveys that need a clean, unbranded look — e.g. government/B2B). Default on for free tier.
- CTA links to registration with a UTM/referrer tag (`source=viral_loop`, plus which page) so the channel is measurable — depends on [referrer tracking](feature-referrer-tracking.md) / [UTM link generator](feature-utm-link-generator.md).
- Keep it visually minimal so it does not erode respondent trust in the survey.

## Notes

- Cheapest, fastest-compounding idea in the growth epic.
- The public results page is brand-new and indexable (in sitemap) — pairs naturally with [public results showcase + SEO](idea-public-results-showcase-seo.md).
- Conversion will be modest because most respondents are general public, not creators — that's expected; the value is that it's free and always-on.
- Should be implemented through OpenSpec (`/opsx:new`) since it touches public templates.
