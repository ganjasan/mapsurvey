## Why

/for-educators/ validated the audience-page pattern (SEO surface + segment conversion + attribution).
Extend it to the two most-validated remaining segments: urban planners (the core Maptionnaire market —
Lyon, Ivry, Berlin Senate, Decisio, the Jaakko profile) and researchers (participatory-mapping/PPGIS +
citizen science, where the ecosystem work points). The Solutions dropdown was built to hold this family.

## What Changes

- New public pages **/for-planners/** and **/for-researchers/** — tailored positioning, honest use
  cases, UTM-tagged CTAs (`utm_source=planners` / `utm_source=researchers`), first-touch source capture.
- Both added to the Solutions nav dropdown, the footer Product column, `sitemap.xml`, and `robots.txt`.
- SEO blocks per page (title/meta/keywords/canonical/OG) for planning and research search intent.

## Capabilities

### New Capabilities
- `audience-pages`: Segment-specific public landing pages (planners, researchers) with SEO, UTM
  attribution, and sitemap/robots discoverability, reusing the for-educators pattern.

## Impact

- Views/URLs: `for_planners`, `for_researchers` + routes; sitemap/robots entries; nav + footer links.
- Templates: `for_planners.html`, `for_researchers.html` (extend `base_landing.html`).
- Depends on Phase-1 attribution (shipped). Content grounded in real users + verified facts.
