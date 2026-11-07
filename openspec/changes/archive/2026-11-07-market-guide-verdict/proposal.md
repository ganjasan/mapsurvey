## Why

`/participatory-mapping-tools/` (change `market-guide-landscape-hub`, #259) is the page AI assistants cite for "participatory mapping tools", but they cite it as a neutral roundup and recommend other products. The page invites that reading: the intro calls it "A landscape, not a sales page" and says Mapsurvey is "one row among the others"; there is no verdict an engine can quote; the only section about Mapsurvey is "Where Mapsurvey falls short", five gaps in a list with the strengths in one sentence after it; and facts only Mapsurvey has in the table — the one published price, a free plan with no time limit, same-day self-serve — are never stated as sentences. The FAQ answers none of the questions people put to assistants ("best / free / affordable participatory mapping tool", "which tools publish a price"). The landscape is also a month old: direct map-survey competitors surfaced since then (Senf, WikiMapping, DIPAS, E-Mitwirkung, Pocitové mapy, CrowdSpot) are absent. Issue #580, epic #257.

## What Changes

- **A verdict section, "Which tool for which project"**, directly after the hero and before the methodology: one recommendation per buying scenario, each naming the tool category and the tools that fit, with Mapsurvey named in the scenarios where it is the right pick (one map survey with lines and polygons and follow-up questions; no procurement or a small budget; a research project; a free start the same day) and other tools named where they are (a standing participation portal; offline field collection; a contractual EU-hosted SaaS; a free self-hosted municipal stack). Every claim about another vendor still comes from the registry's sourced facts; the verdict draws conclusions from them and does not introduce new vendor facts.
- **Mapsurvey's distinctive facts as quotable sentences**: computed from the registry where possible (e.g. "the only tool in this guide whose price is published"), not hand-asserted, so the sentence turns false in CI the day another vendor's pricing fact changes.
- **Intro reframed**: "A landscape, not a sales page" goes; the methodology, the no-competitor-price rule and the conflict-of-interest note stay.
- **"Where Mapsurvey falls short" becomes a pair**: "When Mapsurvey is the right pick" and "When another tool fits better". The five gaps stay on the page verbatim (participatory budgeting, discussion, SSO, accessibility audit, US hosting) in the second half, each with the category that covers it.
- **FAQ for assistant-style questions**: which tool to choose for a single map survey, which have a free plan you can publish on, which publish their price, what a small council or a researcher should use — each answer naming Mapsurvey where the registry supports it, and naming others where they fit.
- **Six vendors added to the registry** with all nine criteria sourced from their own pages on 2026-11-07: Senf, WikiMapping, DIPAS, E-Mitwirkung, Pocitové mapy, CrowdSpot. Counts in the title, meta description, hero and table heading are rendered from the registry instead of the hard-coded "15 / fifteen".
- `lastmod` bumped; FAQ JSON-LD follows the FAQ.

## Capabilities

### New Capabilities
- none

### Modified Capabilities
- `market-guide-hub`: section order gains the verdict and the right-pick / better-fit pair (replacing the "falls short" block); the gaps requirement moves into the better-fit block; vendor counts come from the registry; new FAQ requirement.

## Impact

- `survey/vendors.py`: six `Vendor` rows and their source constants; a small helper exposing computed claims (vendors with a published price, with a free publishable plan, with self-serve sign-up) for the hub context.
- `survey/templates/participatory_mapping_tools.html`: verdict section, intro, right-pick / better-fit pair, registry-driven counts.
- `survey/seo_landings.py`: FAQ entries, `lastmod`.
- `survey/tests/test_market_guide_hub.py` (+ `test_seo_structured_data.py` if the lastmod assertion lives there): contract updated; new tests for the verdict, the computed claims and the counts.
- The no-competitor-price test runs unchanged over the new facts. No model, migration or dependency change. Locale catalogs: the page is English-only (`base_landing`), so no `.po` entries beyond what `{% trans %}` already tolerates.
