## Context

The four category landings were rewritten in change `seo-landings-rewrite` (#251, merged 2026-10-06) around one section order, one pricing partial, one sibling partial and one CSS block, so that "the next page (#252 citizen engagement) is a template away". This change is that page.

**Baseline (Search Console via PostHog, `googlesearchconsole_search_analytics_by_query_country` / `_by_query_page`, 2026-07-03 … 2026-10-03, `country != 'mar'`):** every query containing "citizen" is a conversational AI-Mode question; together they make about 40 impressions and 0 clicks over three months, at positions 1–5 for the affordability, free-trial and data-ownership questions and 78 for "best citizen engagement platform for mid-sized city". The impressions land on `/for-government/` (27, position 16.9), `/civic-engagement/` (6, 8.5), `/community-engagement-platform/` (4, 3.0). The head term "citizen engagement platform" has no impressions; "delib citizen space mapping features" (5, position 10) lands on the civic page.

| Question Search Console shows | Section that answers it |
|---|---|
| free trials or freemium plans for governments | Procurement: "Free plan, not a trial"; FAQ |
| most affordable for local governments / counties under 100k / smaller jurisdictions | Procurement: one price for every size; pricing partial; FAQ |
| cost-effective alternatives to enterprise platforms | Comparison table; "when they fit better" |
| data ownership and export controls | Procurement: data ownership; FAQ |
| reliable uptime for municipalities | Procurement: uptime and support; FAQ |
| community mapping and issue reporting | Hero, use cases |

Constraints: no EU-hosting claim (`/trust/`: United States today, self-host for residency); no competitor price figures (owner rule 2026-10-06: pricing model, free tier and "listed or on request" only; the figures on the #251 and alternatives pages predated the rule and are removed here too, on the owner's call of 2026-10-06); competitor facts dated "as of October 2026"; the repo is public, no lead names; the Pro figure lives in `_landing_pricing.html` only.

## Goals / Non-Goals

**Goals:**
- One page that is the best answer to "citizen engagement platform" for a local-government buyer: definition, product, comparison, procurement answers, price, proof, FAQ, 1,500+ words.
- The three overlapping pages have three distinct intents and say so; a reader on any of them can reach the other two.
- A 28-day before/after measurement: the citizen-query cluster should move from `/for-government/` to the new page, and the head term should start appearing.

**Non-Goals:**
- No new screenshots, CSS, partials or JSON-LD types. No `/pricing/` page. No change to the four #251 pages beyond one cross-link sentence on two of them. No new comparison pages (#253).
- No RU translation; the landings are English-only.

## Decisions

**D1 — Same template skeleton as the #251 pages.** `citizen_engagement_platform.html` extends `base_landing.html` and follows the D1 order of `seo-landings-rewrite` (hero → definition → how it works → feature grid → comparison → use cases → pricing → siblings → From the field → FAQ) with one page-specific section inserted after the comparison: **Procurement**, six short blocks that answer the Search Console questions in the buyer's words (free plan vs trial, price for a small jurisdiction, data ownership and export, uptime and support, hosting and residency, accessibility). Why a section and not only FAQ: the FAQ is a list of answers; a buyer skimming the page needs the headings.

**D2 — Incumbents: Go Vocal and Citizen Space.** Go Vocal (ex-CitizenLab) is the vendor that named the category; Citizen Space (Delib) is the one the cluster's own queries name ("delib citizen space mapping features") and the default UK local-government platform. Both are already described, with dated facts, on the civic and consultation pages, so the cells are consistent across the site. Rows as in #251 (free tier, pricing model, open source / self-hosting, respondent map input, GIS export, respondent account, languages, hosting region, accessibility) — the pricing row names the **model** only: "quote only, listed on G-Cloud", "per-instance licence, quote only". Alternative considered: Go Vocal + Open Point as the issue text suggests — rejected, Open Point is already the CEP page's comparison, and Citizen Space is literally in the cluster.

**D3 — Three pages, three intents, stated in prose.** Community engagement platform = the category and product page (what the software does); civic engagement = the concept and methods (how to engage people on a map); citizen engagement platform = the local-government buyer and procurement (how to buy it: trial, price, data, uptime). The citizen page's definition section says this in one paragraph and links to the other two with their head terms as anchor text; the community and civic pages get one sentence each pointing the procurement reader here. The sibling partial gets the fifth entry so all five pages link to each other. Why: Google cannibalisation is a ranking split across near-duplicate pages; distinct H1s, distinct definitions and explicit cross-links are the documented remedy.

**D4 — Honest uptime copy.** No uptime figure and no SLA claim: the hosted service has no contractual SLA today; deploys are zero-downtime, the stack is monitored, a self-hosted instance runs under the council's own policy, and Pro buys direct support from the developer. Why: a number we do not measure publicly is a claim a buyer will ask us to prove.

**D5 — Topic binding.** `topics.py`: `Topic("citizen-engagement", "Citizen engagement", "citizen_engagement_platform")`. The From the field block renders once a production story is tagged (admin action, like the #258 reminder).

**D6 — Title and description.** Title "Citizen Engagement Platform — Free for Local Government, Open Source | Mapsurvey"; description ≤ 160 characters naming the map input, the free plan and the flat price without the figure (D3 of #251: one file for the figure).

**D7 — Tests extend the existing contract class.** `SeoCategoryLandingContractTest.PAGES` and `SIBLINGS` gain the fifth page (the loop asserts incumbents, screenshots, pricing block, siblings, audience page `/for-government/`, 1,500 words, dated note); `test_price_lives_in_the_partial_only` reads the fifth template; new tests: no registry template and no FAQ answer contains a currency figure other than $0 / $49 / $490 — the only prices on any landing are ours; the FAQ carries free-trial, small-jurisdiction, data-ownership and uptime questions; the community and civic pages link to `/citizen-engagement-platform/` in their body text, and the sibling block of the citizen page excludes itself.

## Risks / Trade-offs

- [The page cannibalises the two it is meant to complement] → distinct H1 and definition, intent sentence on all three, cross-links; measured at 28 days by page.
- [The cluster is tiny (40 impressions in three months)] → the bet is the head term and the AI-Mode questions, which already rank 1–5 with nothing to land on; the cost is one template.
- [Competitor cells go stale] → dated note, "not published" cells, facts shared with the civic and consultation pages so one correction fixes all.
- [Uptime section reads as weak against "99.9%" claims] → it names what is true and what Pro buys; a buyer who needs an SLA is told to self-host or write to us.

## Migration Plan

Merge = deploy. No migration, no env var. `lastmod` 2026-10-06 in the registry; sitemap and robots derive from it. Rollback = revert. After deploy: request indexing of the page in Search Console; tag the Whitehouse and Olney stories with `citizen-engagement` in the admin (they are parish/town-council projects). Measurement: the baseline query above, 28 days after deploy, by page and by `query ILIKE '%citizen%'`.

## Open Questions

- Which production stories carry `citizen-engagement`: proposed Whitehouse CC (parish council) and Olney (town council); owner's call in the admin.
