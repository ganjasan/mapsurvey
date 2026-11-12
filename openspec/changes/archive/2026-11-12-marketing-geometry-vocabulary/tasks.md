## 1. Site copy

- [x] 1.1 Homepage `landing.html` (EN) and its `ru` catalog entries
- [x] 1.2 Category landings: `community_engagement_platform.html`, `citizen_engagement_platform.html`, `civic_engagement.html`, `public_consultation_software.html`, `participatory_budgeting.html`
- [x] 1.3 Audience pages: `for_planners.html`, `for_researchers.html`, `for_government.html`, `for_educators.html`, `for_consultants.html`
- [x] 1.4 Comparison pages: `maptionnaire_alternative.html`, `social_pinpoint_alternative.html`, `metroquest_alternative.html`, `participatory_mapping_tools.html`; `partials/_landing_pricing.html` and the plan cards it includes (`partials/_plan_cards.html`, also on `/pricing/` and the billing page)
- [x] 1.5 `survey/seo_landings.py` — FAQ answers and summaries
- [x] 1.6 `survey/vendors.py` — criteria, category descriptions, Mapsurvey's facts, synonym restatements of other vendors' geometry cells
- [x] 1.7 Blog articles under `survey/blog/`

## 2. Ops repo

- [x] 2.1 `../Mapsurvey-ops/docs/marketing/product-marketing.md` — customer-language section with the word map and the counts
- [x] 2.2 `directory-listings.md` and other copy-bearing marketing docs (not prospect dossiers)

## 3. Check

- [x] 3.1 Update the Social Pinpoint description assertion in `test_seo_category_landings.py`
- [x] 3.2 Run the landing, SEO, vendor and blog test modules once
- [x] 3.3 Grep the templates for leftover "point/line/polygon" outside export sentences (pages rendered by the test run; no browser pass)
