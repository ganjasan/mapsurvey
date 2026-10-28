## Why

Coursework is the one acquisition pattern the data proves works (the FTSPK class = 33% of all
registrations), but there's no inbound surface a lecturer can find and self-qualify on. Search today
confirms the gap: for coursework queries ("map survey for classroom", "walkability survey tool for
students") Mapsurvey is weak-to-absent while Maptionnaire, ArcGIS Survey123, and Make Place rank via
dedicated content pages (see `docs/gtm/for-educators-seo-monitoring.md`). A focused `/for-educators/`
landing page is the scalable inbound complement to the outbound plays (Cahyono follow-up + cluster
radar) in the growth epic's H1.

## What Changes

- New public page **`/for-educators/`** — "Mapsurvey for classrooms": positioning (Google Forms for
  geodata, free for education, no GIS skills), an anonymized classroom case study (the FTSPK field
  study), and assignment ideas (walkability / accessibility / pedestrian safety / asset mapping).
- **SEO**: education-intent `<title>`, meta description/keywords, canonical + Open Graph, added to
  `sitemap.xml` and allowed in `robots.txt`.
- **Attribution**: CTAs link to registration tagged `utm_source=edu&utm_medium=for_educators`; the
  page view also captures first-touch referrer (reusing Phase-1 `capture_signup_source`), so
  education/organic signups land in the funnel dashboard's registrations-by-source.
- **Monitoring plan** (doc): baseline SERP captured today, target query set, Google Search Console
  setup steps, and a lightweight recurring rank check to wire up post-deploy.

## Capabilities

### New Capabilities
- `for-educators-page`: A public, SEO-optimized "Mapsurvey for classrooms" landing page with
  UTM-tagged registration CTAs and first-touch source capture, discoverable via sitemap/robots.

### Modified Capabilities
<!-- None at spec level. sitemap_xml / robots_txt gain one URL each; their requirements are unchanged. -->

## Impact

- **Views/URLs**: `for_educators` view + `for-educators/` route; `/for-educators/` added to
  `sitemap_xml` and `robots_txt`.
- **Template**: `for_educators.html` (extends `base_landing.html`, overrides SEO blocks, reuses landing CSS).
- **Depends on**: Phase-1 `SignupAttribution` (shipped) — makes the page's signups measurable.
- **External follow-up (not code)**: Google Search Console verification + sitemap submission by the owner.
