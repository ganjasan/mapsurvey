## Why

Google already serves mapsurvey.org at positions 1–5 for conversational, AI-Mode queries about citizen engagement platforms ("which citizen engagement platforms offer free trials or freemium plans for governments?", "top citizen engagement platforms for community mapping and issue reporting?", "which citizen engagement platforms are most affordable for local governments?", "compare the most popular citizen engagement platforms for data ownership and export controls" — Search Console 2026-07-03 … 10-03, Morocco excluded), but the clicks land nowhere: the impressions are split across `/for-government/` (27, position 16.9), `/civic-engagement/` (6) and `/community-engagement-platform/` (4), and the word "citizen" appears in two meta-keyword lists and on no page body. The head term "citizen engagement platform" itself does not appear in Search Console at all. Go Vocal (ex-CitizenLab) and Citizen Space build their whole category on the word; the buyers who use it are local-government procurement people asking procurement questions — free trial, price for a small jurisdiction, data ownership, uptime. Issue #252, epic #257.

## What Changes

- A new category landing `/citizen-engagement-platform/` in the `seo_landings.py` registry, same section order and shared blocks as the four pages rewritten in #251 (change `seo-landings-rewrite`): hero, definition naming the head term and its variants ("citizen participation platform", "citizen engagement software for local government"), how-it-works with the four product screenshots, feature grid, comparison table against Go Vocal and Citizen Space with a "when they fit better" note, a procurement section answering the questions Search Console shows (free plan vs trial, pricing for small jurisdictions, data ownership and export, uptime and support, hosting and residency, accessibility), use-case list, the shared pricing and sibling partials, the "From the field" block, FAQ of seven page-specific questions. 1,500+ visible words.
- The three pages stop competing for one query: community = the category/product page, civic = the concept and methods, citizen = the local-government buyer and procurement. Each says so and links to the other two: the sibling partial gains the fifth entry, and one sentence in the definition section of the community and civic pages points buyers to the citizen page by its head term.
- No price figure for any other vendor on the page (owner rule of 2026-10-06, restated in #253): the pricing row says how each vendor prices (per instance, per licence, quote only, listed on G-Cloud) and whether a free tier exists. The same rule is applied retroactively to the figures the #251 pages and the alternatives pages still carried (Social Pinpoint, Go Vocal, Citizen Space, Commonplace, Maptionnaire cells and two FAQ answers), and a test over every registry template and FAQ answer keeps it that way.
- The `citizen-engagement` story topic gets the new landing as its page, so stories tagged with it appear in the page's "From the field" block and their chips link here.
- Registry: FAQ, breadcrumbs, `lastmod` 2026-10-06; sitemap and robots follow automatically. URL + view in the existing pattern (`utm_source=citizen_engagement`).
- Tests: the new page joins the category-landing contract test (incumbents, screenshots, pricing block, siblings, word count, dated note, no EU-hosting claim), plus a check that no landing template or FAQ answer carries a currency figure other than our own and that the citizen FAQ answers the free-trial, small-jurisdiction, data-ownership and uptime questions.
- Baseline recorded in the design for the 28-day after-measurement.

## Capabilities

### New Capabilities
- `citizen-engagement-landing`: the content contract of the citizen engagement platform page — the category contract plus the procurement section, the three-page intent split and the no-competitor-price rule.

### Modified Capabilities
- none in the main specs. The category contract of change `seo-landings-rewrite` (not yet archived) is reused by inclusion, not modified: this change adds a fifth page that satisfies it.

## Impact

- New: `survey/templates/citizen_engagement_platform.html`.
- `survey/seo_landings.py`: one registry entry. `survey/topics.py`: `citizen-engagement` → `citizen_engagement_platform`. `survey/urls.py`, `survey/views.py`: route and view.
- `survey/templates/partials/_landing_siblings.html`: fifth category entry. `community_engagement_platform.html`, `civic_engagement.html`, `for_government.html`: one cross-link sentence each. Pricing cells reworded on `community_engagement_platform.html`, `civic_engagement.html`, `public_consultation_software.html`, `maptionnaire_alternative.html`, `social_pinpoint_alternative.html`; two FAQ answers in `seo_landings.py`.
- `survey/tests.py`: `SeoCategoryLandingContractTest` extended; new assertions for the citizen page.
- No model, migration, CSS or dependency change.
