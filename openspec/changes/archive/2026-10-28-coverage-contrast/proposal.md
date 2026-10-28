## Why

On a real survey the Responses coverage surface is close to invisible. A research survey with
21 participants who drew 35 polygons for one question shows "≤ 12 of 35 respondents", and its
strongest cell is barely darker than the basemap at 100 % layer opacity. GitHub #370.

Two defects and one missing control:

- `L.SprayAgreementLayer._bin` counts members, and coverage passes one member per SHAPE. A person
  with two overlapping areas counts twice in a cell, and the denominator is the number of shapes,
  not people. The `responses-coverage-surface` spec already says each respondent counts once.
- Opacity is the absolute share, `count / respondents`. Full colour needs every respondent on one
  cell, which a real survey rarely reaches, so the whole surface stays pale. The public results
  grid already scales to the strongest cell.
- Where the transition from "a few people" to "most people" sits is an analytical choice, and the
  creator has no way to make it.

## What Changes

- Binning groups members by id: a respondent counts once per cell however many shapes they drew,
  and `M` in "≤ N of M respondents" is distinct respondents in scope.
- Coverage surfaces scale opacity to the strongest cell in view: that cell is full colour, a cell
  covered by the fewest respondents is the faint minimum. Spray agreement surfaces keep the
  absolute share (option `scale`, default `share`).
- The coverage settings popover gains two controls that together shape the opacity curve:
  **Contrast** (an exponent on the curve, with a live preview of the curve) and **Minimum
  respondents** (cells below N are not drawn).
- The `responses-coverage-surface` change (merged, not archived) gets its rendering sentence
  amended so the two specs agree.

## Capabilities

### New Capabilities
- `responses-coverage-contrast`: how a coverage surface maps respondent counts to opacity and the
  controls a creator has over that mapping.

### Modified Capabilities
- None in `openspec/specs/`. The unarchived `responses-coverage-surface` delta is amended in place.

## Impact

- `survey/assets/js/spray_layer.js`: `_bin` grouping, the alpha mapping as one pure helper, new
  options `scale`, `gamma`, `minCount`.
- `survey/templates/editor/partials/analytics_geo_map.html`: coverage slot options, settings
  popover controls and curve preview.
- No model, query, export or public-results change. Settings live with the slot for the page's
  life, like cell size and corridor today.
