## 1. Shared blocks

- [x] 1.1 Move `.cmp*` and `.aud-*` rules into `landing.css` under one "Category landings" block; add two-card pricing and sibling-links styles
- [x] 1.2 `partials/_landing_pricing.html`: Free $0 / Pro $49 per month or $490 per year per workspace, early access, Pro button to `/pro/`
- [x] 1.3 `partials/_landing_siblings.html`: the other three category pages + the audience page passed by the including template

## 2. Competitor facts

- [x] 2.1 Collect dated, sourced facts for Social Pinpoint, EngagementHQ, Go Vocal, Consul, Citizen Space, Commonplace, Decidim, Balancing Act (pricing, map input, export, open source, hosting, languages, respondent account); record sources in the PR
- [x] 2.2 Write the eight-row comparison table and the "when X may fit better" note per page; "not published" where the vendor says nothing

## 3. Page rewrites

- [x] 3.1 `community_engagement_platform.html`: full rewrite per design D1; drop the EU-hosted badge and copy; US-hosted / self-host wording
- [x] 3.2 `public_consultation_software.html`: full rewrite (council / online / digital consultation variants)
- [x] 3.3 `civic_engagement.html`: full rewrite (map-based community engagement, how to engage people on a map)
- [x] 3.4 `participatory_budgeting.html`: full rewrite (software / platform / tool / map variants, honest scope)
- [x] 3.5 Titles and meta descriptions for the four pages and `social_pinpoint_alternative.html`

## 4. Registry

- [x] 4.1 Rewrite the FAQ entries of the four pages in `seo_landings.py` (6–7 variant-query questions each, page-specific answers)
- [x] 4.2 `lastmod="2026-10-06"` on the five entries

## 5. Tests and verification

- [x] 5.1 `SeoCategoryLandingContractTest` in `survey/tests.py`: one test per spec scenario (GIVEN / WHEN / THEN)
- [x] 5.2 Run the SEO/landing test classes, then the full suite once
- [x] 5.3 Open the four pages on the dev server at desktop and 390px width; check the table scrolls, the pricing cards stack, no console errors
- [x] 5.4 Validate the FAQPage JSON-LD of one page with a JSON parse of the rendered block
- [x] 5.5 PR notes: baseline table, the after-measurement query and date, the admin topic-tagging reminder
