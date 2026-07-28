## Why

Two rendering defects make the respondent-facing form look broken in exactly the
configurations we recommend to serious users. Both surfaced while building a demo survey
for a prospective German client (ThINK Jena, kommunale Wärmeplanung), but neither is
specific to that survey — any author hitting the same, entirely ordinary, patterns sees
the same result.

1. **`rating` clips worded labels** (backlog #85). A Likert scale with worded anchors
   ("very unsure" … "very confident") renders as five equal-width boxes with the text cut
   off mid-word. Worded anchors are the *normal* form of a rating scale, so this is not an
   edge case.
2. **Sub-question popup is 300px wide** (backlog #86). Sub-questions of a geo question are
   the only route for attributes to reach the exported GeoJSON `properties`
   (`survey/views.py:941`), so every survey that produces a usable attribute layer is
   pushed into this pattern. With 6-8 sub-questions the respondent scrolls a narrow column
   floating over the map, which also hides the feature being described.

## What Changes

- **Rating options size to their content and wrap.** Replace the fixed `flex: 1` /
  `min-width: 0` sizing with content-driven sizing plus word wrapping, so long labels wrap
  (and, when needed, the row wraps) instead of overflowing their box.
- **Sub-question popup gets a sensible width and a viewport-based height.** Set `maxWidth`
  (currently unset, so Leaflet's 300px default applies) and `minWidth`, and derive
  `maxHeight` from the viewport rather than the document. Applied at both `bindPopup` call
  sites, which are currently duplicated.

Explicitly **not** in scope: exposing popup width/height as author-facing settings. The
survey author cannot know the respondent's screen and would mostly leave the default alone;
the default has to be right on its own. Also out of scope: moving the attribute form from
the popup into a side panel — worth doing, but a separate, larger change.

## Capabilities

### Modified Capabilities
- `survey-response-form`: rating options wrap instead of clipping; geo sub-question popups
  size to the viewport instead of Leaflet's default.

## Impact

- `survey/assets/css/main.css` — rating layout rules (~line 318-345). Requires
  `collectstatic`.
- `survey/templates/base_survey_template.html` — `bindPopup` options at both call sites
  (~line 383 and ~line 513).
- No model, migration, or API changes. No data migration. Purely presentational.
- Risk: low, but the CSS change alters the visual width of rating buttons for every
  existing survey using that type — they become content-sized rather than equal-width.
  Numeric scales (1-5) keep looking essentially the same because their labels are equally
  short.
