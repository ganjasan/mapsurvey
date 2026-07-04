# Tasks — for-educators-landing

## 1. Page

- [x] 1.1 `for_educators` view (renders `for_educators.html`, calls `capture_signup_source` for first-touch attribution)
- [x] 1.2 Route `for-educators/` in `survey/urls.py`
- [x] 1.3 Template `for_educators.html` extending `base_landing.html`: hero, why-it-fits, anonymized case study, assignment ideas, UTM CTAs; reuses landing CSS + small scoped styles

## 2. SEO / discoverability

- [x] 2.1 Override `title` / `meta_description` / `meta_keywords` / `canonical_url` / `og_*` for education intent
- [x] 2.2 Add `/for-educators/` to `sitemap_xml`
- [x] 2.3 Allow `/for-educators/` in `robots_txt`

## 3. Tests

- [x] 3.1 `ForEducatorsLandingTest`: renders 200 with SEO + `utm_source=edu` CTA; present in sitemap + robots

## 4. Monitoring

- [x] 4.1 Baseline SERP captured + monitoring plan: `docs/gtm/for-educators-seo-monitoring.md`
- [ ] 4.2 (Owner) Google Search Console: verify domain, submit sitemap, request indexing of the page
- [ ] 4.3 (Post-deploy) wire the lightweight recurring rank check for the target queries
- [ ] 4.4 Watch `edu` in the funnel dashboard's registrations-by-source after deploy
