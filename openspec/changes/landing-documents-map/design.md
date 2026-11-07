## Context

`landing-core` (#576) gave `Landing` + ordered `LandingBlock`s with per-kind JSON data passing
`landings.clean_block`. A file needs a `FileField`, so documents get a row per file; a map
needs geometry, small enough to live in the block's JSON (the layer-memory rules: no
multi-megabyte text per row on a page every visitor loads).

## Decisions

### D1. `LandingFile` rows under a documents block
`LandingFile(block FK CASCADE, file FileField public tier key landing_files/<uuid>.<ext>, title
≤ 200, size, content_type, order)`. The block's `data` is `{}`; the files ARE the content. One
form saves the block: rename (`file_title_<id>`), remove (`remove_<id>`), add (`files`,
multiple; title defaults to the file name without extension). A block left with no file is
refused.

### D2. What a document may be
Extensions `pdf docx xlsx pptx odt ods odp doc xls ppt csv txt`, ≤ 25 MB, ≤ 20 files per block.
The first bytes must match the family: `%PDF-` for PDF, `PK\x03\x04` for the OOXML/ODF zip
formats, `D0 CF 11 E0` for legacy Office, and for csv/txt the first 4 KB must decode as UTF-8
and contain no `<` tag-like markup (`<html`, `<script`, `<svg`). The served content type comes
from the extension (storage backend), never from the browser's claim. Links open the file in a
new tab; the visible name is the title.

### D3. The map block keeps a normalised GeoJSON in `data`
Upload `geojson_file` (≤ 1 MB). Accepted: a FeatureCollection, a Feature or a bare geometry;
geometry types Point, LineString, Polygon and their Multi-forms; ≤ 500 features; every
geometry valid for GEOS and inside lon −180..180 / lat −90..90. Stored as a FeatureCollection
whose features carry only `geometry` and `properties.name` (from `name`, `title` or `Name`,
≤ 120 chars), coordinates rounded to 6 decimals; an edit without a new file keeps the stored
one. Options: `color` (#rrggbb, default #2f6fb0), `basemap` (a key the workspace resolves,
default `streets`), `caption` ≤ 300.

### D4. Rendering
`landings/blocks/map.html` prints the FeatureCollection with `json_script` and a div; the
public page loads Leaflet 1.4.0 (the version the respondent and results pages use) only when a
map block is on it, builds the tile layer from `basemaps.resolve(key, org).leaflet()` with the
Mapbox token added on the client as `public_results.html` does, draws the features with the
colour (polygons 0.15 fill), names as tooltips, `fitBounds` with padding, scroll-wheel zoom off.

## Risks / Trade-offs

- [A renamed HTML file served from our media host] → magic-byte check per family (D2).
- [Large GeoJSON on every visit] → 1 MB upload cap, 500 features, 6-decimal rounding.
- [Basemap style deleted later] → `resolve` falls back to `streets` on render.
