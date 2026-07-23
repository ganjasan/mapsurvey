## Why

The 12 SEO landing pages shipped in the recent wave have clean per-page `title`/`meta`/`canonical`, but no page-level structured data beyond the site-wide `SoftwareApplication` + `Organization` markup in `base_landing.html`. Two high-value, low-cost gaps remain: (1) no `FAQPage` markup or FAQ content, so we forgo FAQ rich results and leave long-tail intent ("is it free?", "can I self-host?", "do respondents need an account?") unanswered on-page; (2) no `BreadcrumbList`, so SERP entries — especially the two-level `alternatives/*` pages — show a bare URL instead of a breadcrumb trail. Separately, the landing-URL list is hardcoded in three places (`urls.py`, `robots_txt`, `sitemap_xml`), so adding a landing can silently miss the sitemap or robots allow-list, and sitemap entries carry no `lastmod`/`priority` hints.

## What Changes

- Add a reusable **FAQ section partial** and render it on each of the 12 SEO landing pages with 3–5 page-specific Q&A targeting long-tail intent (competitor-comparison specifics on `alternatives/*`).
- Emit **`FAQPage` JSON-LD** built from the same per-page Q&A list, so the on-page FAQ and the structured data never drift.
- Emit **`BreadcrumbList` JSON-LD** on landing pages (`Home › [Solutions|Alternatives] › Page`).
- Introduce a **`{% block structured_data %}`** in `base_landing.html` so pages opt into per-page JSON-LD without touching the site-wide markup.
- Establish a **single source of truth** for the SEO landing URLs (one Python list/registry) consumed by `urls.py` route registration is out of scope, but `robots_txt` and `sitemap_xml` SHALL both derive their landing list from it.
- **Sitemap polish**: add `<lastmod>`, `<changefreq>`, `<priority>` to landing entries.
- Add tests mirroring `SeoProductLandingPagesTest` / `OrganizationSchemaTest`: assert FAQ + `FAQPage` present and well-formed, `BreadcrumbList` present, and that the sitemap/robots contain every registered landing.

No user-facing behavior changes beyond added on-page FAQ content; no breaking changes.

## Capabilities

### New Capabilities
- `seo-structured-data`: Page-level structured data for the SEO landing pages (FAQ section + `FAQPage` JSON-LD, `BreadcrumbList` JSON-LD, opt-in `structured_data` block) and a single-source-of-truth landing registry that drives `sitemap.xml` and `robots.txt` with `lastmod`/`changefreq`/`priority` hints.

### Modified Capabilities
<!-- None: the existing `landing-page` spec covers the root `/` page and its structure; this change adds a separate SEO-metadata capability layered over the marketing landings and does not alter root-page requirements. -->

## Impact

- **Templates**: `survey/templates/base_landing.html` (new `structured_data` block, FAQ include hook); new partials `survey/templates/partials/_faq_section.html` and `partials/_landing_structured_data.html`; the 12 landing templates opt in by supplying a Q&A list.
- **Views / Python**: `survey/views.py` (`robots_txt`, `sitemap_xml` refactored to consume a shared landing registry; new registry module e.g. `survey/seo_landings.py`).
- **Tests**: `survey/tests.py` (new test class for structured data + sitemap coverage).
- **No** model/migration/DB impact; **no** new dependencies.
