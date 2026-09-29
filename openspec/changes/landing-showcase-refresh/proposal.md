## Why

"See it in action" and "Capabilities" were last updated in July. Since then Mapsurvey gained reference layers with object cards, reactions to objects, the shared map, branching, star ratings and rankings, respondent photos, a new Responses workspace with map selection, export to Excel/GeoPackage/Shapefile/KML, and public results pages — none of it is on the landing page, which still says "13 question types" and "GeoJSON + CSV". The Copenhagen demo (change `copenhagen-demo`) now shows all of it on real data, so the landing can show the same survey a visitor can open.

## What Changes

- **See it in action**: four steps instead of three — Build (layer editor with the Copenhagen bridges), Collect (a respondent's bridge card), Analyze (the Responses map), Share (the public results page) — with new copy and new 1920×1200 / 1200×750 screenshots taken from the demo. Heading: "From a brief to published results".
- **Capabilities**: six cards rewritten around jobs — Questions made for maps; Your data on the map; A map people build together; Built to be answered; Clean and analyse; Export and publish. Heading: "Everything a map-based consultation needs". Every claim checked against the product (e.g. 1 926 marker icons → "almost two thousand").
- **Bug fix found while taking the screenshots**: the Responses Overview map thumbnail often stayed on the world view with no answers drawn. `EditorMap.whenSized` measured `map.getSize()`, which Leaflet caches at construction (0×0 inside a hidden pane), so `ready` never ran unless an unrelated `invalidateSize()` won the race; and the Overview set its world view *after* `mount()`, which undid the fit whenever `ready` ran synchronously.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `landing-page`: a product showcase of four steps and a capabilities grid of six cards, screenshots taken from the demo survey.
- `responses-overview`: the thumbnail scenario covers a map built inside a hidden pane and a container that is already laid out.

## Impact

- `survey/templates/landing.html`, `survey/assets/img/landing/{build,collect,analyze,share}{,-full}.webp` (new `share*`).
- `survey/assets/js/editor_map.js` (`hasSize`), `survey/templates/editor/partials/analytics_overview_pane.html` (start view in map options).
- Tests: landing render test for the four steps and six cards; guard tests for the two map fixes.
