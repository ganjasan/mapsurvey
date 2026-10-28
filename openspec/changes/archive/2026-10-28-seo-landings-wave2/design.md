## Context

Wave 1 established the `seo-landing-pages` capability: thin `capture_signup_source` views,
templates extending `base_landing.html` with per-page SEO blocks, hand-maintained
`sitemap_xml`/`robots_txt` lists, footer internal links, and one test class per batch. Wave 2 adds
five pages on that contract, prioritized by a fresh Keyword Planner measurement (2026-07-21):
civic-engagement cluster (10k–100k/mo), participatory budgeting (1k–10k, ~$50 bids),
social pinpoint (1k–10k brand), metroquest (sunset brand → migration searches), consultants
(validated outbound segment). Competitor facts come from `docs/marketing/competitors/openpoint.md`
(hands-on verified, July 2026).

## Goals / Non-Goals

**Goals**
- Own the civic-engagement semantic cluster (largest measured gap) with a middle-funnel category page that funnels to the wave-1 product pages.
- Capture two competitor-brand searches with honest, dossier-backed comparison pages.
- Add the consultants audience page (nav dropdown + footer).

**Non-Goals**
- No EngagementHQ / Bang the Table comparison yet — no product dossier; writing it without verified facts risks false claims. Backlog until researched.
- No PPGIS page — volume too small (100–1k, declining), already covered by `/for-researchers/`.
- No blog infrastructure; no RU translations.

## Decisions

### Decision: Funnel roles per page
- `/civic-engagement/` is the **category anchor** (middle funnel): explains map-based civic
  engagement methods and links *down* to both product pages and *across* to audience pages. H1 keeps
  the bare head term "civic engagement" for the 10k–100k cluster (`civic engagement`,
  `civic involvement`, `civic participation`, `civic engagement platform`).
- `/participatory-budgeting/` is a **use-case page**. Honesty constraint: Mapsurvey has no
  budget-allocation module (Open Point's "Fund It" does coin-style allocation). The page frames PB as
  *map-based location input for PB programmes* (where residents want investment) and says plainly
  that dollar-allocation exercises are not a built-in feature. Overclaiming here would burn exactly
  the audience the page attracts.
- `/for-consultants/` is an **audience page**: consultancies run engagements for clients, so the copy
  leads with per-project economics (no per-project fees → margin), GeoJSON deliverables for the
  client's GIS, and open-source self-hosting for running it under the consultancy's own instance.

### Decision: Comparison pages reuse the maptionnaire pattern verbatim
Same structure (hero → why-switch cards → side-by-side table → "being fair" → founder-contact
block), same `utm_source=comparison` with per-page `utm_medium`. Competitor claims are restricted to
dossier-verified facts with the dossier's own wording discipline:
- Social Pinpoint: "current-generation Social Map limits respondents to point markers" (verified in
  live config), "no GeoJSON export" (XLSX/CSV/PDF; shapefile legacy-only), quote-gated pricing with
  reported $15–40K/yr budgets, multilingual as a paid add-on (≤15 languages) vs our 75 free. The
  "being fair" list credits their real strengths: pin voting modes, Fund It budgeting, WCAG 2.2 work,
  AI analysis, the 40+-tool hub.
- MetroQuest: migration framing — metroquest.com redirects to openpoint.com; the 5-screen format is
  being rebuilt as Flex Forms; classic constraints (no post-launch edits, 2 languages, weeks of lead
  time) vs Mapsurvey (self-serve, editable, 75 languages, draw input, GeoJSON). "Being fair" admits
  we also have no drag-coins budget-allocation or visual-preference screens.
- Each table keeps the wave-1 style disclaimer note with an as-of date.

### Decision: Navigation placement follows the wave-1 rule
Audience pages → nav "Solutions" dropdown; category/use-case/comparison pages → footer only. So
`/for-consultants/` joins the dropdown; the other four go to the footer "Product" list.

### Decision: `robots.txt` relies on the existing `/alternatives/` prefix
The two comparison pages need no new robots lines. The three new top-level paths get explicit
`Allow:` lines, matching how every existing landing is listed.

## Risks / Trade-offs

- **Competitor pages can go stale** (Open Point ships fast post-PE). Mitigated by the as-of
  disclaimer note and by keeping claims to structural facts (pricing model, export formats, input
  geometry) rather than screenshots or minor features.
- **PB page attracts users wanting allocation mechanics we lack.** Mitigated by explicit honesty in
  the copy; the page's job is to capture the *map-based* subset of PB demand and be truthful about
  the rest.
- **Footer link list is growing** (11 links). Acceptable for now; if it doubles again, split the
  footer column into Product / Compare groups (noted for a future change, not done here).

## Migration Plan

Pure addition, one deploy. No migrations, no static-asset changes (`landing.css` reused).

## Open Questions

- EngagementHQ dossier → future `/alternatives/engagementhq/` (volume 100–1k, Medium competition,
  ~1 261 грн bids measured 2026-07-21). Needs competitor research first.
