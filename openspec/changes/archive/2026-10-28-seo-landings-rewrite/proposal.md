## Why

Four of the twelve SEO landing pages rank on page 3–5 of Google for their own head term (Search Console 2026-09-06 … 10-03, 28 days): `/community-engagement-platform/` 403 impressions at position 16.4, `/public-consultation-software/` 303 at 19.8, `/civic-engagement/` 190 at 14.9, `/participatory-budgeting/` 48 at 5.5 — 13 clicks between them. `/alternatives/social-pinpoint/` sits at position 3.8 for "social pinpoint alternative" with 0 clicks from 47 impressions. The pages are thin (a hero, two feature rows, a FAQ: 740–830 words of template) while the pages that beat them carry a definition, pricing, a comparison table, screenshots, case studies and 1,500+ words. Issue #251, epic #257.

## What Changes

- Each of the four category pages is rewritten around its head term and the close variants Search Console already shows it for (`public engagement platform`, `local government community engagement platform`, `community engagement platform pricing`, `council consultation software`, `online public consultation platform`, `map based community engagement`, `participatory budgeting software`…): a definition section, a how-it-works walk-through with product screenshots, a feature grid, a comparison table against the two incumbents of that category with a "when they fit better" note, a pricing section, a use-case list, links to the three sibling category pages and the matching audience page, the existing "From the field" story block, and a FAQ of 6–7 page-specific questions. Target: 1,500+ words of visible copy per page.
- One pricing partial shared by the four pages: Free ($0) and Pro ($49 a month or $490 a year per workspace, unlimited users, surveys and responses), the prices already on file with the payment provider; the Pro column links to `/pro/`.
- One sibling-links partial: the four category pages link to each other and to their audience page.
- Comparison-table and feature-grid styles move from per-template `<style>` blocks into `landing.css` so the four pages share one look.
- `/community-engagement-platform/` stops claiming EU hosting (hero badge, body copy): the wording follows `/trust/` — hosted in the United States today, self-host for EU residency.
- Titles and meta descriptions of the five pages are rewritten for click-through (the head term first, then the price or the "free / open source" hook); `/alternatives/social-pinpoint/` gets a title and description naming the price and the point-marker limit.
- The FAQ entries of the four pages in `seo_landings.py` are rewritten to answer the variant queries (cost, council, free, map input); `lastmod` of the five entries is bumped to the ship date.
- Baseline recorded in this change's design for the 28-day before/after measurement.

## Capabilities

### New Capabilities
- `seo-category-landings`: the content contract of the four category landing pages (sections, pricing, comparison, siblings, hosting claims, FAQ) and the CTR rules for their titles and descriptions.

### Modified Capabilities
- none — the sitemap, robots, FAQ JSON-LD and story-block requirements are unchanged; only the registry entries' content and `lastmod` values change.

## Impact

- Templates: `community_engagement_platform.html`, `civic_engagement.html`, `public_consultation_software.html`, `participatory_budgeting.html` (rewritten), `social_pinpoint_alternative.html` (title/description only), new `partials/_landing_pricing.html`, `partials/_landing_siblings.html`.
- `survey/seo_landings.py`: FAQ entries and `lastmod` of five entries.
- `survey/assets/css/landing.css`: shared comparison, feature-grid, steps and pricing styles.
- `survey/tests.py`: a test class for the content contract (sections present, prices, two incumbents, sibling links, no EU-hosting claim, word count, lastmod).
- No model, migration, URL or view change. No new dependency.
