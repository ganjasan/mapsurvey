## 1. Binning and opacity (`survey/assets/js/spray_layer.js`)

- [x] 1.1 `_bin` groups members by id; one `seen` set per group; `n` = groups in scope
- [x] 1.2 Pure `L.SprayAgreementLayer.alphaFor(count, n, max, opts)` with `scale`, `gamma`, `minCount`
- [x] 1.3 `_redrawGrid` draws through `alphaFor`; defaults keep spray unchanged (the heat style keeps its own fringe ramp)

## 2. Coverage slot and settings (`editor/partials/analytics_geo_map.html`)

- [x] 2.1 `createCoverage` passes `scale: 'max'`
- [x] 2.2 Settings popover: Contrast slider (−100…100 → gamma 4^(v/100)) and Minimum respondents slider (1…M, max follows stats)
- [x] 2.4 Coverage tops out at 0.9 opacity (spray keeps 0.75); the cell slider's range reaches the automatic cell size
- [x] 2.3 Curve preview SVG redrawn on every setting change and stats event

## 3. Specs, tests, verification

- [x] 3.1 Amend the rendering sentence in the unarchived `responses-coverage-surface` spec
- [x] 3.2 `CoverageSurfaceTest`: contract tests for grouping, `alphaFor`, `scale: 'max'` and the two controls
- [x] 3.3 Behaviour check of `alphaFor` and `_bin` grouping under node
- [x] 3.4 Browser check on a local rebuild of the 21-respondent survey: before/after screenshots
