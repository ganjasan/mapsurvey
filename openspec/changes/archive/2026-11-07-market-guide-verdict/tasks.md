## 1. Registry

- [x] 1.1 Add `price_listed`, `free_publishable`, `self_serve` flags (default `False`) to `Vendor`; set them on Mapsurvey and on every existing vendor whose sourced facts support them
- [x] 1.2 Add the six vendors (Senf, WikiMapping, DIPAS, E-Mitwirkung, Pocitové mapy, CrowdSpot) with all nine criteria sourced from their own pages, read 2026-11-07; flags set from the same facts
- [x] 1.3 `hub_context()`: vendor/category/criteria counts and the three computed vendor lists

## 2. Page

- [x] 2.1 Title, meta description, hero and table heading render counts from the context; no spelled-out counts
- [x] 2.2 Verdict section `id="verdict"` after the hero: one recommendation per scenario, Mapsurvey where the facts support it, other vendors in at least three scenarios, names looked up from the registry
- [x] 2.3 Intro: drop "A landscape, not a sales page" and "one row among the others"; keep method, price rule, conflict-of-interest note; computed-fact sentences
- [x] 2.4 Replace the "falls short" block with `id="right-pick"` and `id="better-fit"` (gaps + the category that covers each)
- [x] 2.5 FAQ: four assistant-style questions in `seo_landings.py`; bump `lastmod`

## 3. Tests

No new tests for the copy (owner, 2026-11-07); the existing contract is only kept green.

- [x] 3.1 Minimal edits to `MarketGuideHubTest` so it passes (better-fit instead of gaps, lastmod from the registry)
- [x] 3.2 Run once: `survey.tests.test_market_guide_hub`, `test_seo_structured_data`, `test_citizen_engagement_landing` (price scan), `test_template_hygiene`, `test_landing_page`
