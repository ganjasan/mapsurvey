## Why

Google has two result pages for the query `mapsurvey`. In the brand version mapsurvey.org is #1; in
the generic version Google reads the query as "survey map" and we are not on page 1. A DataForSEO
measurement on 2026-10-26 (585 samples, 189 countries) got the brand version in only ~38% of
searches, with little difference between English and other Google UIs. The name is two ordinary
words, so Google is not sure "Mapsurvey" is a product; the structured data we ship is part of how
it decides (issue #443).

## What Changes

- The homepage pair (`/`, `/ru/`) emits `WebSite` JSON-LD with `name: "Mapsurvey"` and the
  `alternateName` values, the signal Google documents for the site name shown in results.
- `Organization` and `SoftwareApplication` get stable `@id`s and are linked (`publisher`, `author`),
  so the graph says "Mapsurvey the software is made by Mapsurvey the organisation at mapsurvey.org".
- `SoftwareApplication` describes the hosted web service we actually are (`WebApplication`,
  category `BusinessApplication`, `operatingSystem: "Any (web browser)"`, `url`) instead of a
  developer tool for "Linux, Docker".
- The `sameAs` profile list moves from the template into one Python registry, so adding a profile
  (Wikidata, LinkedIn, a directory listing) is a one-line change with a test that keeps the URLs
  well-formed.
- Not in this repo: a Wikidata item draft and a profile/listing checklist go to the private ops
  repo for the owner to submit by hand. No changelog card — creators see nothing.

## Capabilities

### New Capabilities
- `brand-structured-data`: the JSON-LD every marketing page carries about the Mapsurvey brand —
  Organization, SoftwareApplication, WebSite on the homepage pair — and the single registry of
  profiles it links to.

### Modified Capabilities
<!-- none: no existing spec states structured-data requirements -->

## Impact

- `survey/templates/base_landing.html` (the two JSON-LD blocks), `survey/templates/landing.html`
  (WebSite block for the homepage pair), a new registry module `survey/brand.py`, the context that
  renders `base_landing.html` pages.
- Tests in `survey/tests.py` parse the rendered JSON-LD.
- No models, migrations, settings or dependencies.
