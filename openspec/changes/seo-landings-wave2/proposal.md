## Why

Wave 1 (`seo-engagement-landings`) shipped the two bottom-funnel product pages. A follow-up
Keyword Planner measurement (2026-07-21, worldwide) priced the rest of the strategy map from
`docs/marketing/seo-keyword-research.md`:

- `civic engagement` / `civic involvement` — **10k–100k/mo each**, low competition, zero coverage on our site. The single largest gap.
- `participatory budgeting` — 1k–10k/mo with top bids ~**$50/click**, low competition.
- `social pinpoint` — 1k–10k/mo brand searches; our Open Point dossier gives verified comparison facts.
- `metroquest` — 100–1k/mo and **-90% YoY**: the brand is being sunset into Open Point (metroquest.com now redirects), which means orphaned customers actively searching for a replacement.
- `engagement consultant` — 100–1k/mo with high bids; consultancies are also our validated outbound segment (`docs/marketing/prospects/`).

Five landing pages capture these on the already-proven pattern.

## What Changes

- Add a category page `/civic-engagement/` (middle-funnel semantic anchor: civic engagement / civic involvement / civic engagement platform).
- Add a use-case page `/participatory-budgeting/` (map-based PB framing; honest about not having a budget-allocation module).
- Add an audience page `/for-consultants/` (engagement & planning consultancies; joins the nav "Solutions" dropdown).
- Add `/alternatives/social-pinpoint/` and `/alternatives/metroquest/` comparison pages on the `maptionnaire_alternative` pattern, using verified facts from `docs/marketing/competitors/openpoint.md` with the same "being fair" honesty section.
- Register all five in `sitemap.xml`; allow the three non-`/alternatives/` URLs in `robots.txt` (`/alternatives/` is already allowed as a prefix).
- Internal links: footer "Product" list gains all five; nav "Solutions" dropdown gains "For Consultants" (audience pages only, per wave-1 design decision).
- Enrich meta keywords of the wave-1 pages with newly-measured variant terms (`citizen engagement software`, `online consultation`) — metadata only, no behavior change.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `seo-landing-pages`: five additional landing-page requirements (category, use-case, audience, and two competitor-comparison pages) following the contract established in wave 1.

## Impact

- `survey/views.py` — five view functions; `sitemap_xml` + `robots_txt` lists.
- `survey/urls.py` — five `path()` entries.
- `survey/templates/` — five new templates; `base_landing.html` footer + nav dropdown links.
- `survey/templates/community_engagement_platform.html`, `public_consultation_software.html` — meta keyword additions.
- `survey/tests.py` — new `SeoWave2LandingPagesTest`.
- No model, migration, or dependency changes.
