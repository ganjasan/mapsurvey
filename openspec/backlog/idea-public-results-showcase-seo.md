# Public results showcase gallery + SEO

**Type**: idea
**Priority**: medium
**Area**: general
**Epic**: growth
**Created**: 2026-06-10

## Description

Use the (already built) public results pages as an organic acquisition channel. A curated, indexable showcase gallery of real aggregated results — plus per-page SEO — turns finished surveys into discoverable content that pulls in prospective creators searching for participatory-mapping / geo-survey examples.

## Evidence (from 2026-06-10 analysis)

- The public results page (`/r/<slug>/`) is new and already indexable (included in sitemap, `public` visibility) — an organic channel is effectively baked into the product, just not yet leveraged.
- We have real, compelling result sets to showcase: Lyon transit accessibility (658 responses), snowdrop citizen science, school-route safety, walkability audits.
- Acquisition is currently unmeasured/under-leveraged on the organic side (most attention has gone to direct outreach).

## Scope / plays

- **Showcase gallery**: an opt-in public index of example results pages (creator consent required — privacy first), grouped by use case (mobility, citizen science, community mapping).
- **SEO basics on results pages**: descriptive titles, meta descriptions, Open Graph cards (map thumbnail + headline stat) so they preview well when shared and rank for use-case queries.
- **Content angle**: short write-ups / case studies around standout public results (e.g. the Lyon survey) — doubles as outreach and Reddit/community material (see `reference_reddit_subreddits`).
- Pairs with the ["Made with Mapsurvey" viral loop](feature-made-with-mapsurvey-viral-loop.md) — the results page is the prime CTA placement.

## Notes

- Privacy is the hard constraint: only showcase results from creators who explicitly opt in; respect k-anonymity masking already in `PublicResultsService`. Never showcase `unlisted` pages.
- Measure organic lift via [referrer tracking](feature-referrer-tracking.md) (search/Direct breakdown).
- Lower urgency than coursework (#1) and the viral loop (#2), but compounds over time and reuses existing product surface.
- **2026-08-10 — partially shipped.** The SEO half is done: results pages carry titles, meta and OG cards (`survey/templates/public_results.html:8-20`) and are in the sitemap (`survey/views.py:1754-1764`); a stories hub with a `results` story type exists (`survey/urls.py:111-112`, `survey/models.py:713`). The showcase gallery as specified — creator opt-in consent, grouped by use case — is not built; stories are staff-curated instead.
