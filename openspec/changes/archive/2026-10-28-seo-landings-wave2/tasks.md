# Tasks

## 1. Views & URLs
- [x] 1.1 Add five views in `survey/views.py` (`civic_engagement`, `participatory_budgeting`, `for_consultants`, `social_pinpoint_alternative`, `metroquest_alternative`) — `capture_signup_source` + `render`.
- [x] 1.2 Add five `path()` entries in `survey/urls.py`.
- [x] 1.3 Add five URLs to `sitemap_xml`; add `Allow:` lines for the three non-alternatives paths in `robots_txt`.

## 2. Templates
- [x] 2.1 `civic_engagement.html` — category page, H1 "civic engagement", funnel links to both product pages, `utm_source=civic_engagement`.
- [x] 2.2 `participatory_budgeting.html` — use-case page, honest no-allocation-module note, `utm_source=participatory_budgeting`.
- [x] 2.3 `for_consultants.html` — audience page, margin/deliverables/self-host framing, `utm_source=consultants`.
- [x] 2.4 `social_pinpoint_alternative.html` — comparison page on the maptionnaire pattern, dossier-verified claims, "being fair" section, `utm_medium=social_pinpoint_alt`.
- [x] 2.5 `metroquest_alternative.html` — migration-framed comparison page, `utm_medium=metroquest_alt`.
- [x] 2.6 `base_landing.html` — "For Consultants" in the Solutions dropdown; all five pages in the footer "Product" list.
- [x] 2.7 Meta keyword enrichment: `citizen engagement software` on `community_engagement_platform.html`, `online consultation` on `public_consultation_software.html`.

## 3. Tests
- [x] 3.1 `SeoWave2LandingPagesTest` in `survey/tests.py` — per page: 200, positioning text, canonical, UTM.
- [x] 3.2 Sitemap/robots discoverability assertions for all five.
- [x] 3.3 Footer + nav-dropdown link assertions.

## 4. Verify
- [x] 4.1 `./run_tests.sh` targeted classes — new tests pass, wave-1 and other landing tests unaffected.
- [x] 4.2 `openspec validate seo-landings-wave2 --strict` passes.

## 5. Design polish (post-review)
- [x] 5.1 `landing.css`: `.showcase--center` modifier centering `.section-eyebrow`/`.section-heading` (max-width heading needs margin auto); applied to all 12 audience/product/comparison landings — root landing untouched. collectstatic run.
- [x] 5.2 Replace bottom "For local government" secondary CTAs with page-specific "Talk to us…" mailto buttons (civic-engagement, participatory-budgeting, public-consultation-software).
