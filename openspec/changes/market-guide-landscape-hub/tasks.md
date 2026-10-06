## 1. Registry

- [x] 1.1 `survey/vendors.py`: `Fact`, `Vendor`, `Category`, `Criterion` dataclasses; `CATEGORIES` (5), `CRITERIA` (8 + the verified column is derived), `VENDORS` (15, facts from the 2026-10-06 verification, every fact with URL + date); import-time validation; helpers `get_vendor`, `vendors_in`, `sources_for`, `facts_verified_on`
- [x] 1.2 `seo_landings.py`: `participatory_mapping_tools` entry (path, breadcrumbs, seven FAQ entries, `lastmod="2026-10-06"`); `ALTERNATIVES` crumb → ("Participatory mapping tools", "/participatory-mapping-tools/"); `lastmod="2026-10-06"` on the three alternatives entries; `render_seo_landing` passes `vendors`, `categories`, `criteria`, `mapsurvey` into the context
- [x] 1.3 `urls.py` + `views.py`: hub route and view; `/alternatives/` → `RedirectView(permanent=True)`

## 2. Pages

- [x] 2.1 `partials/_vendor_vs_table.html`: criteria × (Mapsurvey, vendor) table + sourced note; replace the hardcoded tables in `maptionnaire_alternative.html`, `social_pinpoint_alternative.html`, `metroquest_alternative.html`; correct the Maptionnaire hero badge/card (no EU hosting) and the Social Pinpoint GeoJSON card; intro line + CTA link to the hub on all three
- [x] 2.2 `participatory_mapping_tools.html`: head blocks (title, description ≤160, canonical, og), hero, how-to-read, five category sections, criteria section, the vendors × criteria table with `title` provenance and Verified column, gaps block, sources list (`id="sources"`), compare-in-detail, pricing partial, siblings partial, FAQ; 1,500+ words
- [x] 2.3 `base_landing.html` footer link; `_landing_siblings.html` hub entry; `landing.css` rules for the wide table (sticky first column) and the sources list

## 3. Tests and verification

- [x] 3.1 `VendorRegistryTest`: completeness, https sources, ISO dates not in the future, categories exist, every alternatives landing's vendor exists; extend `test_no_competitor_price_figure_on_any_landing` over registry fact texts and the rendered hub
- [x] 3.2 `MarketGuideHubTest`: the contract scenarios (render, sitemap/robots/hreflang, gaps block, sources complete, links up/down, 301, alternatives tables from the registry, Maptionnaire page without Frankfurt, Social Pinpoint page without "no GeoJSON", a patched fact reaching both pages); update `test_breadcrumb_single_and_two_level`, the hreflang path list and any string the wave-2 tests asserted in the old tables
- [x] 3.3 Run the landing/SEO test classes, then the full suite once
- [x] 3.4 Open the hub and the three alternatives pages on the dev server at desktop and 390 px; table scrolls, sources links resolve, no console errors; parse FAQPage + BreadcrumbList JSON-LD
- [ ] 3.5 PR notes: baseline, after-measurement query and date, the list of corrected cells, the request-indexing reminder
