# Tasks

## 1. Views
- [x] 1.1 Add `community_engagement_platform(request)` view in `survey/views.py` — `capture_signup_source(request)` then `render(request, 'community_engagement_platform.html')`.
- [x] 1.2 Add `public_consultation_software(request)` view in `survey/views.py` — same pattern, renders `public_consultation_software.html`.
- [x] 1.3 Add both URLs to `sitemap_xml` (`/community-engagement-platform/`, `/public-consultation-software/`).
- [x] 1.4 Add both URLs to `robots_txt` `Allow:` lines.

## 2. URLs
- [x] 2.1 Add `path('community-engagement-platform/', views.community_engagement_platform, name='community_engagement_platform')` to `survey/urls.py`.
- [x] 2.2 Add `path('public-consultation-software/', views.public_consultation_software, name='public_consultation_software')` to `survey/urls.py`.

## 3. Templates
- [x] 3.1 Create `survey/templates/community_engagement_platform.html` extending `base_landing.html` — H1 "Community Engagement Platform", cross-audience body, self-canonical, `utm_source=engagement_platform` CTA, cross-links to `/for-government/` and `/for-planners/`.
- [x] 3.2 Create `survey/templates/public_consultation_software.html` extending `base_landing.html` — H1 "Public Consultation Software", consultation-workflow body, self-canonical, `utm_source=consultation_software` CTA, cross-link to the platform page.
- [x] 3.3 Add both pages to the `base_landing.html` footer "Product" list.

## 4. Tests
- [x] 4.1 Add a `SeoProductLandingPagesTest` (`survey/tests.py`) — for each page: `200`, H1/positioning text, self-canonical URL, `utm_source=…` present.
- [x] 4.2 Assert both pages appear in `/sitemap.xml` and are allowed in `/robots.txt`.
- [x] 4.3 Assert the shared footer links to both pages (render any landing page, check both hrefs).

## 5. Verify
- [x] 5.1 Run `./run_tests.sh survey` — new tests pass, no regressions in existing landing/sitemap/robots tests.
- [x] 5.2 `openspec validate seo-engagement-landings --strict` passes.
