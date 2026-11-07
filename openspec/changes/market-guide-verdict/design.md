## Context

The hub was built (change `market-guide-landscape-hub`) as a deliberately neutral buyer's guide: one fact registry, every cell sourced, Mapsurvey one row with its gaps in prose. That worked for ranking and for being cited — and it is exactly why assistants quote the table and pick vendors with longer cells. An engine summarising the page needs a sentence that says which tool fits which job; we never wrote one, so it writes its own.

Owner decision 2026-11-07: an **honest verdict**, not a sales page. Sources and rules stay; the page now draws conclusions, and in the scenarios where Mapsurvey is the right pick it says so.

## Goals / Non-Goals

**Goals**
- Give engines and readers a quotable verdict per buying scenario, near the top, that names Mapsurvey where the facts support it.
- State Mapsurvey's distinctive facts as sentences that are computed from the registry, so they cannot silently become false.
- Keep the gaps on the page, next to the strengths instead of alone.
- Bring the landscape up to date with six direct competitors.

**Non-Goals**
- No competitor price figures (owner rule 2026-10-06), no ranking scores or star ratings, no "best overall" claim.
- No new `/alternatives/` pages; no change to the alternatives renderers.
- No change to the registry's validation rules or the criteria set.

## Decisions

1. **Verdict as data in the view context, prose in the template.** Each scenario is a short template block (heading, one-sentence answer, the tools it names). Tool names in a scenario are looked up from the registry by key, so a scenario cannot name a vendor that is not in the table. Alternative considered: scenarios as a tuple in `vendors.py` — rejected, they are editorial copy, not vendor facts, and the registry's rule is "facts only".
2. **Computed claims come from `hub_context()`** over four explicit `Vendor` flags (`price_listed`, `free_publishable`, `self_serve`, `draws_shapes`, default `False`), each set by hand next to the sourced fact that supports it — reviewable in one diff, where parsing fact text would be brittle.
   - "Mapsurvey is the only tool that publishes its price" turned out false (KoboToolbox, Mergin Maps, Jotform, G-Cloud listings, Pocitové mapy, WikiMapping all list rates), so the page does not say it. The true distinctive claim is the combination: free, same-day and lines and polygons — Mapsurvey, PARTIMAP, KoboToolbox — and the verdict then says what separates Mapsurvey from the other two (GIS formats and a public results page for an anonymous public).
   - Prices: listed per specialised map-survey tool as public vs on request; a vendor that lists rates still shows no figure on our page.
3. **Counts rendered from the registry** (`{{ vendor_count }}`, `{{ category_count }}`, `{{ criteria_count }}`), with numbers spelled as digits in the title ("21 Map-Based Survey and Engagement Platforms"). Words ("fifteen") go.
4. **Right pick / better fit replace "falls short"**. The better-fit list is Mapsurvey's `gaps` tuple, each gap followed by the category that covers it. The existing test words (participatory budgeting, SSO, United States) keep passing, but the block id/heading changes, so the spec scenario is modified.
5. **New vendors' categories** follow the registry's definitions: a vendor whose product is the map survey is `ppgis`; a suite with a map tool among many is `engagement`; DIPAS likely `open_source`. Decided per vendor from what its own pages state.

## Risks / Trade-offs

- **Engines may discount a page that recommends its author.** Mitigation: the verdict names other tools in four of the scenarios, the methodology and conflict-of-interest note stay, and every claim stays sourced. Measure: AI-panel re-run (ops `ai-search-panel`) four weeks after deploy, same questions as 2026-09-05/28; and GSC clicks on the page.
- **New vendors' facts are a month fresher than the rest.** The "Verified" column already shows per-row dates; acceptable.
- **Non-English vendor pages** (DIPAS, E-Mitwirkung, Pocitové mapy) are read in the original language; facts are written in English and the notes keep the quoted sentence for audit.
