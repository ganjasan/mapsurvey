## 1. Landing registry + builders (`survey/seo_landings.py`)

- [x] 1.1 Create `survey/seo_landings.py` with a `SeoLanding` dataclass (`key`, `path`, `url_name`, `changefreq`, `priority`, `lastmod`, `breadcrumbs`, `faq`) and an ordered `SEO_LANDINGS` registry covering all 12 pages (audience: planners/researchers/government/educators/consultants; keyword: community-engagement-platform, public-consultation-software, civic-engagement, participatory-budgeting; alternatives: maptionnaire, social-pinpoint, metroquest).
- [x] 1.2 Author 3–5 page-specific Q&A per entry (long-tail intent: free / self-host / respondent account / data export / GDPR; comparison specifics for `alternatives/*`). Ensure question sets differ across pages.
- [x] 1.3 Set `breadcrumbs` per entry — `Home › <Page>` for audience/keyword pages, `Home › Alternatives › <Page>` for `alternatives/*`.
- [x] 1.4 Implement `build_faqpage_jsonld(faq)` and `build_breadcrumb_jsonld(request, crumbs)` returning `json.dumps` strings (valid JSON, absolute URLs from `request`).
- [x] 1.5 Implement `render_seo_landing(request, key)` that looks up the entry, calls `capture_signup_source(request)`, and renders the page template with `faq_items`, `faqpage_jsonld`, `breadcrumb_jsonld` in context.

## 2. Templates: block + partials

- [x] 2.1 Add `{% block structured_data %}{% endblock %}` to `base_landing.html` immediately after the site-wide `SoftwareApplication` + `Organization` JSON-LD.
- [x] 2.2 Create `survey/templates/partials/_faq_section.html` rendering a visible FAQ `<section>` from `faq_items` (accessible markup; render nothing if `faq_items` is empty).
- [x] 2.3 Create `survey/templates/partials/_landing_structured_data.html` emitting the `FAQPage` and `BreadcrumbList` `<script type="application/ld+json">` from `faqpage_jsonld` / `breadcrumb_jsonld` (guard each so a page without FAQ omits `FAQPage` cleanly).
- [x] 2.4 In each of the 12 landing templates, override `{% block structured_data %}` to `{% include "partials/_landing_structured_data.html" %}` and place `{% include "partials/_faq_section.html" %}` near the closing CTA.

## 3. Wire views to the registry

- [x] 3.1 Refactor the 12 landing view functions in `survey/views.py` to `return render_seo_landing(request, '<key>')`, removing per-view duplication while preserving existing docstrings/UTM behavior.

## 4. Sitemap + robots single source of truth

- [x] 4.1 Refactor `robots_txt` to build its SEO-landing `Allow:` lines from `SEO_LANDINGS` (keep the static `/surveys/`, `/stories/`, admin/editor disallows and the `Sitemap:` line).
- [x] 4.2 Refactor `sitemap_xml` to emit each registry entry as `<url>` with `<loc>`, `<lastmod>`, `<changefreq>`, `<priority>` (keep root, `/trust/`, `/surveys/`, and per-survey entries).

## 5. Tests (`survey/tests.py`)

- [x] 5.1 `LandingStructuredDataTest`: for each landing, assert the FAQ section renders (a known question appears) and a `FAQPage` `<script>` is present, parses as valid JSON, and its question names match the visible FAQ.
- [x] 5.2 Assert `BreadcrumbList` present and valid: 2 items for a single-level page, 3 ordered items (Home/Alternatives/page) for an `alternatives/*` page.
- [x] 5.3 Assert site-wide `SoftwareApplication` + `Organization` JSON-LD still present on landings (no regression).
- [x] 5.4 Assert FAQ question sets are not identical across two sample pages (page-specificity), and that an answer containing an apostrophe still yields valid `FAQPage` JSON.
- [x] 5.5 `SeoLandingRegistryTest`: sitemap contains every registry path with lastmod/changefreq/priority; robots allows every registry path; every registry `url_name` resolves and every SEO landing route is represented in the registry.

## 6. Verify

- [x] 6.1 Run `./run_tests.sh survey` (PostGIS up); fix failures. Spot-check one page's JSON-LD against Google Rich Results Test expectations (valid FAQPage + BreadcrumbList).
