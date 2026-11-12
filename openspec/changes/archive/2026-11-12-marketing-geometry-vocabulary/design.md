## Context

Source of the vocabulary: English `Question.name`/`subtext` of map questions in production (counts in `proposal.md`, issue #650), and Search Console queries for the last 90 days. The marketing copy was written in GIS terms when the product was a PPGIS tool for GIS teams; the buyers who register now are planners, council officers, consultants and teachers who write "Mark the place where…".

## Goals / Non-Goals

**Goals:** one vocabulary for map input across the marketing site, the SEO registry, the vendor registry, the blog and the ops marketing docs.

**Non-Goals:** the editor palette, the help centre and the Wizard (a separate decision); changelog entries; page structure, prices, claims about vendors.

## Decisions

1. **Word map.** point → *mark a place*, *pin* (verb and noun), *place*; line → *draw a route*, *route*; polygon → *outline an area*, *area*. *Path* is a synonym of route only where the context is walking. Spray area keeps its name.
2. **Where GIS terms stay.** Export and format sentences ("GeoJSON with points, lines and polygons"), field-collection tools' own terms (ODK's geopoint/geotrace/geoshape, QField, Mergin, Kobo), and research-facing PPGIS wording on `/for-researchers/`. A researcher's page may say "points, lines and polygons" once, in the data sentence.
3. **Other vendors' facts.** A cell is restated only when the restatement is a synonym of what the vendor's page says (points → places/pins, polygons → areas, lines → routes when the vendor means routes, otherwise "lines"). Source URL and verified date stay — the source was not re-read and the meaning did not change. A cell whose meaning would shift is left as written.
4. **No `lastmod` bump.** CLAUDE.md asks for a bump on a rewrite of a landing (with a new FAQ for variant queries). This is a word-level edit of existing sentences; the sitemap dates stay, and the existing `lastmod` tests stay green.
5. **Translations.** Only the homepage has a Russian twin. Every changed homepage msgid gets its `ru` entry in the same commit (`RussianLandingHreflangTest`); the Russian copy uses *отметить место*, *маршрут*, *область* the same way. Other landings are English-only.
6. **No new tests for copy** (owner rule). One existing assertion changes: the Social Pinpoint description asserts "pins" instead of "point markers".

## Risks / Trade-offs

- A GIS-literate buyer may look for "polygon" → the export sentence and the comparison criterion still carry it once per page.
- Edited msgids drop their compiled translation until the catalog entry is added → only the homepage is translated; the hreflang test catches a miss.
