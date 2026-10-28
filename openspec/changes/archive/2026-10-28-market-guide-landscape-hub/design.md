## Context

Eight pages carry hand-written comparison tables (`table.cmp`, `<td class="mt">` cells, one `.cmp-note` with a free-text date): three `/alternatives/` pages from July 2026 and five category pages rewritten on 2026-10-06 (#251, #252). No vendor data exists in Python. The private ops repo holds ten dossiers, but PR #260 recorded no URL per cell, the landscape research draft cites no URLs at all, and several claims were later retracted (Open Point "no GeoJSON export", Ideenkarte "points only", Go Vocal "no polygons"). Issue #259 asks for one structured file with a public source URL and a `verified` date per fact, rendered on the page.

**Baseline (Search Console via PostHog, `country != 'mar'`).** 28 days 2026-09-06 … 10-03, by query: "public consultation software" 88 impressions / 0 clicks / position 10.2; "public engagement platform" 23 / 0 / 32.8; "community engagement platform" 20 / 0 / 28.0; "participatory mapping tool" 12 / 0 / 43.2; "ppgis" 4 / 0 / 44.2; "best platforms for geolocated community surveys" 3 / 0 / 5.0; "go vocal vs social pinpoint" + reverse 27 / 0 / 27; "social pinpoint pricing" 14 / 0 / 23.5. Three months 2026-07-03 … 10-03 by page: "participatory mapping tool" lands on `/` (65, 39.1), `/for-researchers/` (56, 81.1), `/community-engagement-platform/` (24, 89.4), `/civic-engagement/` (19, 87.2) — four pages, none about the term; "public engagement platform" on the CEP page (50, 36.0); "ppgis" on `/for-researchers/` (4, 55.5) and `/` (1, 9.0). After: same two queries 28 days after deploy, plus `_by_query_page` for the new path.

**Facts verified on 2026-10-06** by reading each vendor's public pages (product page, documentation, UK G-Cloud listing): Maptionnaire, Open Point (Social Pinpoint), Go Vocal, Citizen Space, Commonplace (Zencity), EngagementHQ (Granicus), MetroQuest, ArcGIS Survey123, KoboToolbox, Mergin Maps, Decidim, Consul Democracy, PARTIMAP, Jotform, Google Forms. Notable corrections against what the site says today: Maptionnaire is hosted on AWS in the US and Ireland (not "Finland", and our page's "EU-hosted, Frankfurt" describes nobody); Maptionnaire prices are quote-only (our page says "listed on the vendor's site"); Open Point exports GeoJSON (our card says it does not); Go Vocal respondents draw lines and polygons; Decidim exports coordinates since 0.26.

Constraints: no price figure for any other vendor (owner rule 2026-10-06, `feedback_no_competitor_prices`); no EU-hosting claim for Mapsurvey (`/trust/`: Oregon, United States); no market-size, share or growth figures; no vendor claim without a public URL; the repo is public, no lead names.

## Goals / Non-Goals

**Goals:**
- One page that is the best neutral answer to "participatory mapping tools" / "map-based survey and engagement tools": categories, criteria, one table, sources, links down.
- One data source for vendor facts, with provenance a reader can check, shared by the hub and the alternatives pages.
- The three alternatives pages stop lying about hosting and export.
- A 28-day before/after measurement by query and by page.

**Non-Goals:**
- No `/compare/` pages (#253 builds them on this registry). No `/alternatives/engagementhq/` (#253). No rewrite of the five category pages' tables — their cells were re-read on 2026-10-06 and stay as they are; moving them onto the registry is the follow-up once #253 shows the partial fits a three-column layout.
- No Russian version (needs Wordstat data; epic). No new screenshots, no JSON-LD types beyond FAQPage and BreadcrumbList.
- No vendor the dossiers only know from the AI panel (WikiMapping, Senf, Placecheck, Map-Me, PublicInput, adhocracy+, Ideenkarte): none has a verified page read, and Ideenkarte is a current lead's own project. They are named in prose as "other tools in this category" without claims, or not at all.

## Decisions

**D1 — Path `/participatory-mapping-tools/`, not `/alternatives/`.** The unowned head term with the most impressions is "participatory mapping tool(s)" (164 over three months, spread over four pages that do not use the phrase); "alternatives" as a slug carries no query. `/alternatives/` 301s to the hub so the long-standing breadcrumb parent finally resolves, and the `ALTERNATIVES` crumb is renamed "Participatory mapping tools" and repointed, which changes the BreadcrumbList on the three alternatives pages (test updated). H1: "Participatory mapping tools: a buyer's guide to map-based survey and engagement software". Alternative considered: `/guides/map-survey-tools/` — rejected, no query uses "guide", and a one-level path keeps the breadcrumb two levels deep.

**D2 — Registry shape.** `survey/vendors.py`:

```python
@dataclass(frozen=True)
class Fact:
    text: str      # rendered cell; "Not published" when the page does not say
    source: str    # public https URL the fact was read from
    verified: str  # ISO date it was read

@dataclass(frozen=True)
class Vendor:
    key: str; name: str; maker: str; url: str; category: str
    summary: str                 # one or two sentences for the category section
    facts: dict                  # criterion key -> Fact, every CRITERIA key present
    landing_key: str = ""        # seo_landings key of the /alternatives/ page, if any
    gaps: tuple = ()             # only Mapsurvey carries these
```

`CATEGORIES` (key, title, what the tools are for, who buys them) and `CRITERIA` (key, column heading, one line on what to ask) are tuples of dataclasses too, so the page's section order is data. Module-level validation at import (every vendor has every criterion, every source starts with `https://`, every date parses, every category key exists) — the same "a malformed entry fails CI, not every page" pattern as the changelog loader. Helpers: `get_vendor(key)`, `vendors_in(category)`, `sources_for(vendor)` (deduplicated URLs with the verified date), `facts_verified_on(vendor)` (earliest date, the honest one to print). Why a dataclass per fact rather than a dict of strings: the URL and date are what the issue asks for, and a required field cannot be forgotten.

**D3 — "Not published" is a fact with a source.** When a vendor's public page does not state something (Open Point's line/polygon drawing, Commonplace's languages), the cell says "Not published" and its source is the page we read. The table note explains the convention once. Why: it is the difference between "we did not look" and "we looked and it is not there", and it is what a procurement officer needs to ask the vendor.

**D4 — Pricing cells carry the model only.** Text patterns: "Per licence per year; rate listed on UK G-Cloud, otherwise quote" (Go Vocal, Citizen Space, Commonplace, EngagementHQ), "Annual subscription priced by organisation size, or a fixed 12-month single project; quote only" (Maptionnaire), "By request" (Open Point, MetroQuest), "Per contributor per month, listed on the site" (Mergin Maps), "Free software; partner hosting not priced on the site" (Decidim, Consul), "Free Community plan; paid plans listed on the site" (KoboToolbox), "Published: free, or one flat workspace price" (Mapsurvey). The free-tier column is separate: "Two-week sandbox, cannot publish", "Four-week trial of basic features, mapping excluded", "Free Edition under AGPLv3 to self-host; trial environment via sales", "Free Community plan". `CitizenEngagementLandingTest.test_no_competitor_price_figure_on_any_landing` gains a loop over every `Fact.text` and a pass over the rendered hub, so the registry is under the same rule as the templates.

**D5 — One renderer for the two layouts.** The hub table is vendors × criteria (fifteen rows, eight columns plus "Verified"); the alternatives pages are criteria × two vendors (the transposed form, as today). Both read the same `Fact` objects. `_vendor_vs_table.html` takes `vendor` and `mapsurvey` and renders the criteria rows, the `.cmp-note` with the vendor's source links and verified date, and nothing else; the hub template loops `CATEGORIES`/`VENDORS` itself. Cells on the hub carry a `title` attribute with "Source: <host>, verified <date>" and the row's last column links to the sources list below the table, so a reader can check any cell without leaving the page.

**D6 — Mapsurvey is a row, and its gaps are prose.** The Mapsurvey row uses the `ms` cell class like every comparison on the site, but the hub also has a short "Where Mapsurvey falls short" block naming what the issue lists: no participatory budgeting, no discussion forums or commenting between respondents, no SSO, no formal WCAG conformance audit, hosted in the United States with self-hosting as the residency route. Why: a buyer's guide that hides the author's gaps is a landing page; the AI engines reward the roundups that state them.

**D7 — Alternatives pages: table from the partial, prose corrected, nothing else moves.** The "Why teams switch" cards, "Being fair", maker box, CTAs and FAQ stay; the hero badge "EU-hosted" and the "Self-host or EU cloud … Frankfurt" card on the Maptionnaire page become "Self-host anywhere" (the hosted service is in the US; `/trust/` says so), and the Social Pinpoint card that says "no GeoJSON export" becomes a card about Shapefile and GIS-ready formats. Each page gets one line above the table ("This page is one entry in our guide to participatory mapping tools") and the hub appears in the closing CTA group. `lastmod` bumps to 2026-10-06 on all three.

**D8 — Fifteen vendors, five categories.**
| Category | Vendors |
|---|---|
| Specialised map-based survey tools (PPGIS) | Mapsurvey, Maptionnaire, PARTIMAP |
| Engagement platforms with a map feature | Go Vocal, Open Point (Social Pinpoint), Citizen Space, Commonplace, EngagementHQ, MetroQuest |
| Field data collection | ArcGIS Survey123, KoboToolbox, Mergin Maps |
| Open-source participation frameworks | Decidim, Consul Democracy |
| Generic form builders with a location question | Jotform, Google Forms |

MetroQuest is kept as a row because `/alternatives/metroquest/` exists and must link up; its page still answers (it was not redirected to openpoint.com on 2026-10-06, contrary to the July dossier), so its facts come from metroquest.com. PARTIMAP is the only open-source specialised tool with a public page that states geometry and exports. Mergin Maps stands for the QField family.

**D9 — Links.** Down: hub → every vendor row with a `landing_key` links to its `/alternatives/` page ("Mapsurvey vs Maptionnaire in detail"); a "Compare in detail" section lists all three. Up: alternatives breadcrumb, intro line, CTA; footer "Product" column gains "Participatory mapping tools (guide)"; `_landing_siblings.html` gains the hub entry so all five category pages link to it (and the hub includes the partial with `current="participatory_mapping_tools"`, which renders the five category pages). The hub also links `/for-planners/` and `/for-government/` as the audience pages.

**D10 — Title and description.** Title "Participatory Mapping Tools Compared: 15 Map-Based Survey and Engagement Platforms (2026)"; description ≤ 160 characters naming the criteria and that every fact is sourced and dated. Why the year: roundup queries carry it, and the registry dates make it honest.

## Risks / Trade-offs

- [A vendor disputes a cell] → every cell links its source and date; the fix is one `Fact` and a date bump, visible on every page at once.
- [Facts go stale] → `facts_verified_on` prints the earliest date per vendor on the hub; a quarterly re-read is a Stack item, not code. A test fails if a date is in the future or not ISO; no test fails on age (that would make CI red on a calendar, which `seo_landings` deliberately avoids).
- [The hub cannibalises the CEP page for "public engagement platform"] → the hub's H1 and definition are about tools and categories, the CEP page about the category's product; the hub links to the CEP page as "the category page" in the engagement-platform section. Measured at 28 days by page.
- [Fifteen-row table on a phone] → `.cmp-table-wrap` already scrolls horizontally; the first column is sticky and the category sections above the table carry the same facts in prose, so the table is a reference, not the only reading.
- [MetroQuest facts are thin] → its row says "Not published" in most cells, which is true of its public site and is itself the signal for a buyer.

## Migration Plan

Merge = deploy. No migration, no env var. After deploy: request indexing of `/participatory-mapping-tools/` in Search Console; check that `/alternatives/` 301s in production. Rollback = revert. Measurement: the baseline queries above, 28 days after deploy.

## Open Questions

- none blocking. Whether the five category pages move onto the registry is decided after #253 renders a three-column table from the same partial.
