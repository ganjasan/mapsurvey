## Context

The four category landings (`community_engagement_platform`, `civic_engagement`, `public_consultation_software`, `participatory_budgeting`) and the three alternatives pages are registry-driven (`survey/seo_landings.py`: path, breadcrumbs, FAQ, `lastmod`) and template-bodied (`survey/templates/<key>.html` extending `base_landing.html`). Change `story-topics` (#258) already gave each a "From the field" block. What they lack is substance: the pages that outrank them define the term, show the product, name a price, compare themselves to the incumbents and link sideways.

**Baseline (Search Console via PostHog, `googlesearchconsole_search_analytics_by_page`, web, 2026-09-06 … 2026-10-03):**

| Page | Impressions | Clicks | Avg position |
|---|---|---|---|
| /community-engagement-platform/ | 403 | 2 | 16.4 |
| /public-consultation-software/ | 303 | 3 | 19.8 |
| /alternatives/social-pinpoint/ | 236 | 0 | 15.4 |
| /civic-engagement/ | 190 | 8 | 14.9 |
| /participatory-budgeting/ | 48 | 0 | 5.5 |

**Variant queries each page already appears for (Aug–Oct 2026, ≥3 impressions):** community engagement platform → `public engagement platform`, `map based community engagement`, `community engagement mapping`, `government / local government community engagement platform`, `community engagement platform pricing`, `cost community engagement platform`, `public involvement software`, `public participation software`, `engagementhq platform`, `civic engagement platform`. Public consultation software → `online public consultation platform`, `council consultation software`, `digital public consultation platform`, `public consultation tools`, `consultation software`, `council consultation tool`, `public sector consultation tools`, `interactive planning consultation tool`. Civic engagement → `map based community engagement`, `community engagement mapping`, `participatory mapping tool`, `how to engage people on a map`, `delib citizen space mapping features`. Participatory budgeting → almost nothing yet (`participatory budgeting` 4 impressions); the page is written for `participatory budgeting software / platform / tool / map`. Social Pinpoint → `social pinpoint alternative` (3.8, 0 clicks), `go vocal vs social pinpoint`, `social pinpoint pricing`, `public input alternative`.

Constraints: the pages must not claim EU hosting (`lesson_trust_page_claims`; production is in Render Oregon); competitor facts must be defensible and dated ("as of October 2026"); the repo is public, so no lead names; `/pro/` deliberately quotes no price, but $49/month and $490/year per workspace are on file with the payment provider and were quoted to a paying customer.

## Goals / Non-Goals

**Goals:**
- Each of the four pages reads as the best answer to its head term: definition, product walk-through, comparison, price, proof, FAQ — 1,500+ visible words.
- Variant queries appear in headings, body and FAQ in natural English, once or twice each, never as a keyword list.
- Titles and descriptions give a reason to click (price, free/open source, map input) ahead of the brand.
- One place for the price, one for the sibling links, one stylesheet for the shared blocks, so the next page (#252 citizen engagement) is a template away.
- A before/after measurement is possible: baseline above; after = same query, 28 days after deploy.

**Non-Goals:**
- No new pages (#252–#256 are separate issues). No `/pricing/` page (#157). No change to the alternatives pages beyond the Social Pinpoint title/description. No change to the audience pages' EU-hosting wording (tracked separately as the five-template bug; only the one page in scope is fixed here).
- No new screenshots: the four demo screenshots in `img/landing/` are reused.
- No `gettext` catalog work: the landings are English-only; existing `{% trans %}` usage is kept for consistency, nothing is translated.

## Decisions

**D1 — Section order is the same on all four pages.** Hero (H1 = head term, lead with the map differentiator and the free/open-source hook) → "What is a … / who uses it" definition with the variant terms → "How it works" (four showcase rows reusing `img/landing/build|collect|analyze|share.webp`, linked to the full-size file; no lightbox JS on these pages) → feature grid (six cards) → comparison table vs two incumbents + "When X may fit better" → use cases list → pricing → sibling links → From the field → FAQ. Why: the issue names these blocks; a fixed order lets one CSS block and two partials serve all four and the pages that follow. Alternative considered: a single shared template parameterised from the registry — rejected, the pages need different prose, and a 400-line template with `{% if %}` forests is harder to edit than four files.

**D2 — Incumbents per page.** Community engagement platform: Social Pinpoint (Open Point) and EngagementHQ (Granicus) — both appear in the page's own queries. Civic engagement: Go Vocal and Consul (the civic-participation suites; Consul is open source like us, which keeps the comparison honest). Public consultation software: Citizen Space (Delib) and Commonplace — the UK statutory-consultation incumbents behind `council consultation software`. Participatory budgeting: Decidim and Balancing Act — one open-source suite with a Budgets module, one budget simulator; the table says plainly that Mapsurvey is the "where", not the "how much". Table rows: free tier for real projects · pricing model · open source · self-hosting · respondent map input (point / line / polygon) · GIS export · respondent account · languages. Every cell comes from the vendor's published pages, dated in the note under the table; "not published" is a valid cell. Alternative: Maptionnaire on every page — rejected, it already has its own page and is not what those queries compare against.

**D3 — Pricing partial, prices named.** `partials/_landing_pricing.html`: two cards on the existing `.pricing-card` styles — Free ($0: all question types, map input, every export format, unlimited surveys and responses) and Pro ($49 a month or $490 a year per workspace, unlimited users: public results pages, direct support, and the institutional items as they ship — hosting region, read-only client access, custom domain), the Pro button to `/pro/`. The number lives in this one file. Why name it: Search Console shows `community engagement platform pricing` and `cost community engagement platform`; the AI-panel notes record that engines reward a published small-jurisdiction price and penalise "request a quote"; the figures are already committed to the payment provider. Why not a column of unbuilt features: the card says "as they ship". Rollback: one partial.

**D4 — Sibling partial.** `partials/_landing_siblings.html` renders the four category pages minus the current one (`current` from the template) plus one audience page link passed in. Why a partial: the issue asks for internal links between the siblings; a static list copied four times drifts the first time a page is renamed.

**D5 — Styles to `landing.css`.** The `.cmp*` (table, fair box, maker box) and `.aud-*` (grid, cards, steps, ideas, segments, fair) rules move into `landing.css` under one "Category landings" block; the four templates lose their `<style>` blocks. The alternatives templates keep their inline copies (identical rules, same class names, harmless) — moving them is out of scope.

**D6 — EU hosting wording.** The community-engagement page says what `/trust/` says: hosted in the United States today; self-host for EU residency; region choice is a Pro roadmap item. The other three pages carry no residency claim and get none.

**D7 — Titles and descriptions.** Pattern `<Head term> — <hook> | Mapsurvey`, hook = "Free, Open Source, Map-Based" or the price, description ≤ 155 characters naming the map input, the price and the export. Social Pinpoint: "Social Pinpoint Alternative — Free, Draws Lines and Areas, Not Just Pins | Mapsurvey" with a description naming point-marker input and quote-only pricing. The Pro figure stays out of every meta description too (D3: one file), so a description says "one flat Pro price".

**D8 — FAQ rewrite in the registry.** 6–7 questions per page, each a variant query phrased as a question ("How much does a community engagement platform cost?", "Is there free council consultation software?", "Can residents draw on the map, not just drop a pin?"). Answers are page-specific prose; the shared `_A_*` constants stay for the audience pages. The FAQ JSON-LD follows automatically.

**D9 — Tests encode the contract, not the prose.** One test class: for each of the four pages — status 200, the pricing figures, the two incumbent names, the three sibling paths, the audience path, the screenshot files, no `Frankfurt` / `EU-hosted` / `EU data residency`, visible-text word count ≥ 1,500 (strip tags, drop `<script>`/`<style>`/nav/footer); for the five pages — `lastmod` 2026-10-06 in the sitemap; for Social Pinpoint — the new title. Existing tests on UTMs, canonicals and FAQ parity keep passing.

## Risks / Trade-offs

- [Competitor facts go stale or are wrong] → every table carries an "as of October 2026" note; cells say "not published" rather than guessing; sources recorded in this change's tasks notes.
- [A price on the page contradicts the "research instrument" stance of `/pro/`] → the page says Pro is in early access and links to `/pro/`, which keeps asking the question; the figure matches what the provider and a customer already hold. Owner can revert by editing one partial.
- [Word-count test is brittle] → threshold 1,500 with headroom (pages are written to ~1,700–2,000), counted on visible text only.
- [Pages read as keyword-stuffed] → each variant appears at most twice; the definition section and the FAQ carry them in full sentences.
- [Story block renders empty on production] → the three production stories have no `topics` set (checked 2026-10-06); tagging is an admin action listed in PR #258, noted again in this PR.
- [Shared CSS changes the alternatives pages] → the moved rules are the same declarations; the inline copies on those pages still win by cascade order.

## Migration Plan

Deploy is a merge: no migration, no env var. Bump `lastmod` to the ship date on the five entries (`2026-10-06`); the sitemap updates itself. Rollback = revert the merge. Measurement: re-run the baseline query 28 days after deploy (same table, same filter, dates shifted).

## Open Questions

- Whether the owner wants the Pro figure shown (D3) — proceeding with it shown; one partial to blank.
- Facts that corrected our own notes while researching: Go Vocal's mapping page lists pin, line AND polygon drawing and a Free Edition under AGPLv3; Social Pinpoint's Social Map reporting lists GeoJSON among its exports. The tables follow the vendors' pages, not the older dossiers.
