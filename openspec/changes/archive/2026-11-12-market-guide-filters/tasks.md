## 1. Registry

- [x] 1.1 `Vendor`: `country`, `backing` (Fact), `backing_kind`, `open_source`; `region`, `flag_keys`; backing counted in `sources` and `verified_on`
- [x] 1.2 `REGIONS`, `COUNTRY_REGION`, `BACKING_KINDS`, `FILTER_FLAGS`; validator refuses unknown country/kind and a missing backing Fact
- [x] 1.3 Backing facts for all 22 vendors, read 2026-11-11 from their own pages (Open Point, MetroQuest: the 2026-10-06 pages)
- [x] 1.4 `hub_context()`: `filter_groups` (with counts, only values present) and `non_commercial`
- [x] 1.5 Open-source category text no longer contradicts the DIPAS row

## 2. Page

- [x] 2.1 Tool names link to `Vendor.url` in the table and the category lists; "vs Mapsurvey in detail" stays separate
- [x] 2.2 "Who is behind it" column; country on the maker line; source line per cell on touch screens
- [x] 2.3 Filter bar (hidden in HTML) + `js/market_guide_filters.js`: OR within a group, AND across groups and in "must have", `#tools?…` hash via `replaceState`, empty-state row, row anchors clear a hiding filter
- [x] 2.4 Verdict scenario `id="verdict-public"`, computed from `backing_kind`, with a filter link
- [x] 2.5 `ItemList` JSON-LD from `seo_landings.build_vendor_itemlist_jsonld`
- [x] 2.6 FAQ entry on public and non-profit tools; `lastmod` 2026-11-11
- [x] 2.7 Phone layout below 720 px: cards with `data-label` pairs, explicit ARIA roles, chip groups behind a "Filters (n)" button; short chip labels for categories

## 3. Tests

- [x] 3.1 `MarketGuideFiltersTest`: vendor links, row facets and backing cell, bar hidden without JS, verdict list from the registry, ItemList, validator
- [x] 3.2 Run `test_market_guide_hub`, `test_seo_structured_data`, `test_landing_page`, `test_citizen_engagement_landing`
- [x] 3.3 Look at the page on desktop and phone width with and without a filter (hash on load and on change, empty state, clear, row link clears a hiding filter, cards, folded filters)
- [x] 3.4 Full suite once: `survey billing api mcp newsletter`, 4109 tests OK (before the phone layout; hub modules re-run after it)
