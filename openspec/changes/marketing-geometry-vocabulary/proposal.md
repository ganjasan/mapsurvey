## Why

Creators do not call map input "points, lines and polygons". In the English question text of production surveys they write *mark* (163 surveys), *place* (113), *location* (82), *pin* (60) for a point; *route* (27) and *path* (9) for a line; *area* (55) and *outline* (10) for a polygon. The GIS words come last: *point* 24, *line* 8, *polygon* 10. Our marketing pages lead with the GIS words — "Point, line and polygon input" is a hero badge, the Mapsurvey cell of every comparison table and the answer of several FAQs — so the buyer reads a GIS vendor's vocabulary where they expected their own. Search costs nothing: over 90 days of Search Console (Morocco excluded) the queries that reach us almost never carry a geometry word (21 impressions for pin/mark/place/location, 1 for point, 0 for line or polygon, of ~7,000). Issue #650.

## What Changes

- Marketing copy speaks the creators' words: *mark a place* / *pin* (point), *draw a route* (line), *outline an area* (polygon); as nouns *places, routes, areas*.
- GIS terms stay only where they name the data: the export sentence ("exported as GeoJSON points, lines and polygons"), file formats, and PPGIS wording addressed to researchers.
- Pages: homepage (EN and its RU translation), the four category landings and `/citizen-engagement-platform/`, the five audience pages, the three `/alternatives/` pages, the market guide hub, the pricing partial; the FAQ answers and summaries in `survey/seo_landings.py`; the criteria, category descriptions and Mapsurvey's facts in `survey/vendors.py`; the blog articles that describe drawing.
- Comparison cells of other vendors are restated in the same words where the restatement is a pure synonym (points → places/pins, polygons → areas); the meaning, source and verified date of each fact do not change. Field-collection tools keep their own terms (geopoint/geotrace/geoshape) where the vendor uses them.
- The Social Pinpoint page's meta description says "pins" instead of "point markers".
- Out of the repo: the private ops repo's marketing context and directory-listing copy follow the same rule.
- Not changed: the editor, the help centre, the Wizard, changelog entries (history), `lastmod` dates (a word-level edit is not a rewrite).

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `landing-page`: a requirement that marketing pages describe map input in creators' words and keep GIS terms for the data.
- `seo-category-landings`: the Social Pinpoint description scenario names pins instead of point markers.

## Impact

Templates under `survey/templates/` that extend `base_landing.html`, `survey/templates/partials/_landing_pricing.html`, `survey/seo_landings.py`, `survey/vendors.py`, `survey/blog/*.html`, the `ru` locale catalog for changed homepage strings, one assertion in `survey/tests/test_seo_category_landings.py`. No models, URLs or behaviour change.
