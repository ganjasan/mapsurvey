## 1. Registry and routing

- [x] 1.1 `seo_landings.py`: entry `citizen_engagement_platform` (path, breadcrumbs, seven FAQ entries from the Search Console questions, `lastmod="2026-10-06"`)
- [x] 1.2 `topics.py`: bind `citizen-engagement` to the landing
- [x] 1.3 `urls.py` + `views.py`: route and view in the existing pattern

## 2. Page

- [x] 2.1 `citizen_engagement_platform.html`: hero, definition with the intent split and cross-links, how it works, feature grid, comparison vs Go Vocal and Citizen Space (model-only pricing row, dated note, when-they-fit note, maker box), procurement section (free plan, small jurisdictions, data ownership, uptime and support, hosting, accessibility), use cases, pricing, siblings, From the field, FAQ; title and description
- [x] 2.2 `_landing_siblings.html`: fifth entry
- [x] 2.3 One cross-link sentence in the definition sections of `community_engagement_platform.html` and `civic_engagement.html`, and one under the use cases of `for_government.html` (the page that currently receives the cluster's impressions)

## 3. Tests and verification

- [x] 2.4 Apply the no-competitor-price rule to the #251 pages and the alternatives pages: pricing cells reworded to model + "listed on G-Cloud / not published", two FAQ answers in `seo_landings.py`
- [x] 3.1 Extend `SeoCategoryLandingContractTest` (PAGES, SIBLINGS, price-in-partial list) and add the citizen-specific tests (no currency figure on any landing template or FAQ answer, FAQ questions, body cross-links, topic story)
- [x] 3.2 Run the landing/SEO test classes, then the full suite once
- [x] 3.3 Open the page on the dev server at desktop and 390px; check the table scrolls, no console errors; parse the FAQPage JSON-LD
- [ ] 3.4 PR notes: baseline, after-measurement query and date, the admin topic-tagging reminder, the list of reworded competitor cells
