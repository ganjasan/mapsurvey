## Why

Three `/alternatives/` pages and five category landings compare Mapsurvey with one or two vendors each, but nothing sits above them: a buyer searching the category ("participatory mapping tool" lands on four different pages at positions 39–89, "public engagement platform" at 36, "ppgis" at 44–55; Search Console 2026-07-03 … 10-03) finds no page that surveys the landscape, and the AI engines that answer "tools for map-based surveys" cite neutral roundups, not product landings (the 2026-09 panel names 22+ products instead of us). Every comparison cell on the site is hand-written markup with one free-text "as of July/October 2026" note, so the same vendor is described differently on five pages, the Maptionnaire page still claims "EU-hosted, Frankfurt" fourteen months after production moved to Oregon, and the Social Pinpoint page contradicts itself on GeoJSON export in two sections. Issue #259, epic #257.

## What Changes

- **One vendor fact registry** (`survey/vendors.py`): categories, selection criteria and one `Vendor` per product, every fact a `(text, source URL, verified date)` triple. Facts come only from the vendor's public pages (product page, documentation, UK G-Cloud listing) read on 2026-10-06; a fact the page does not state is rendered as "Not published" with the URL of the page that does not state it. Import-time validation refuses a fact without an `https://` source or an ISO date.
- **A hub page `/participatory-mapping-tools/`**, a buyer's guide rather than a "Mapsurvey vs" page: five categories (specialised map-based survey tools; engagement platforms with a map feature; field data collection; open-source and self-hosted participation frameworks; generic form builders with a location question), each with what the tools are for and who buys them; the selection criteria as the columns of one comparison table; Mapsurvey one row among fifteen, with its gaps stated (no participatory budgeting, no discussion forums, no SSO, no formal accessibility audit); a per-vendor sources list with the verified date rendered; links down to every `/alternatives/` page; FAQ; the shared pricing and sibling sections; 1,500+ visible words.
- **The three `/alternatives/` pages render their comparison table from the registry** through one partial, so the hub and the alternative pages cannot disagree and #196 (stale export claims) cannot recur. In the move the false "EU-hosted / Frankfurt" claims on the Maptionnaire page and the GeoJSON contradiction on the Social Pinpoint page go. Each page links up to the hub (breadcrumb, intro line, closing CTA); the hub, the footer and the sibling partial link down.
- `/alternatives/` (the breadcrumb parent that never resolved) redirects permanently to the hub.
- **Pricing rule enforced on the registry too**: the existing no-competitor-price test extends to every registry fact and to the rendered hub, so a figure in a `Fact.text` fails CI. Competitor pricing cells state the model (per licence / per instance / per contributor / quote only), whether a free tier or trial exists and its conditions, and whether a rate is listed (G-Cloud, the vendor's own pricing page) or available from sales only.
- Registry entries get `lastmod="2026-10-06"` (hub + the three rewritten alternatives pages); sitemap, robots and hreflang follow.
- Baseline recorded in the design for the 28-day after-measurement.

## Capabilities

### New Capabilities
- `vendor-fact-registry`: the contract of the shared vendor data — sourced and dated facts, one renderer for comparison tables, no price figures for other vendors, categories and criteria as data.
- `market-guide-hub`: the content contract of `/participatory-mapping-tools/` — categories, criteria table with Mapsurvey as one row and its gaps named, per-vendor sources with verified dates, links down to every alternatives page, redirect from `/alternatives/`.

### Modified Capabilities
- none in the main specs. The `comparison-pages` contract (change `maptionnaire-alternative-page`) and the Social Pinpoint / MetroQuest requirements of `seo-landing-pages` (change `seo-landings-wave2`), both unarchived, are reused by inclusion: those pages keep their URL, title, "when they fit better" section and UTM attribution; only the source of their table cells changes.

## Impact

- New: `survey/vendors.py`, `survey/templates/participatory_mapping_tools.html`, `survey/templates/partials/_vendor_vs_table.html`.
- `survey/seo_landings.py`: hub entry, `ALTERNATIVES` crumb repointed at the hub, `lastmod` bumps. `survey/urls.py`, `survey/views.py`: hub route + view, `/alternatives/` redirect. `survey/topics.py`: no change (the hub owns no topic).
- `maptionnaire_alternative.html`, `social_pinpoint_alternative.html`, `metroquest_alternative.html`: table replaced by the partial, hosting/export copy corrected, link up to the hub. `base_landing.html` footer: one link. `partials/_landing_siblings.html`: one entry. `landing.css`: a few rules for the wide table and the sources list.
- `survey/tests.py`: new `VendorRegistryTest` and `MarketGuideHubTest`; `LandingStructuredDataTest.test_breadcrumb_single_and_two_level`, the hreflang path list and `CitizenEngagementLandingTest.test_no_competitor_price_figure_on_any_landing` extended.
- No model, migration or dependency change.
