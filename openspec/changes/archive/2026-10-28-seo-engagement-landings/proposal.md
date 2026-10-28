## Why

Keyword research (`docs/marketing/seo-keyword-research.md`) found the highest commercial-intent
terms in our space are `community engagement platform` (~$50/click) and `public consultation
software` (~$23/click, the only "Medium"-competition term). These are bottom-funnel, buyer-intent
queries — municipalities, consultancies, and planning bureaus searching for a product to buy — and
we do not rank for them with a dedicated page. Our current SEO anchor `participatory mapping` is
effectively dead on search demand (Trends index 0.2). Two focused product landing pages capture the
hottest intent using the landing-page pattern we already ship.

## What Changes

- Add a product landing page at `/community-engagement-platform/` targeting the `community engagement platform` head term (cross-audience: councils, NGOs, consultancies, universities, transport agencies).
- Add a product landing page at `/public-consultation-software/` targeting `public consultation software` (consultation-workflow framing: statutory consultation, planning applications, infrastructure).
- Both follow the existing audience-landing pattern: a `capture_signup_source` view rendering a template that extends `base_landing.html`, self-referential `canonical`, and CTAs carrying `utm_source`.
- Register both in `sitemap.xml` and allow them in `robots.txt`.
- Add internal links to both pages from the shared `base_landing.html` footer "Product" list.
- Differentiate from the existing `/for-government/` page (which holds the *audience* framing "community engagement platform **for local government**") so the two reinforce rather than cannibalize: product/category pages own the broad head terms and cross-link to `/for-government/` and `/for-planners/` as audience segments.

## Capabilities

### New Capabilities
- `seo-landing-pages`: standalone SEO product landing pages (distinct from the root `landing-page` capability) — each served at its own URL, extending `base_landing.html`, with page-specific SEO metadata, a self-referential canonical, UTM-tagged CTAs, and inclusion in `sitemap.xml` / `robots.txt`.

### Modified Capabilities
<!-- none — the root landing-page capability (the `/` page) is unchanged. -->

## Impact

- `survey/views.py` — two new view functions; `sitemap_xml` and `robots_txt` gain the two URLs.
- `survey/urls.py` — two new `path()` entries.
- `survey/templates/community_engagement_platform.html`, `survey/templates/public_consultation_software.html` — new templates.
- `survey/templates/base_landing.html` — footer "Product" list gains two internal links.
- `survey/tests.py` — new test coverage (render + SEO + UTM + sitemap/robots discoverability).
- No model, migration, or dependency changes.
