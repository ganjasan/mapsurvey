## 0. Prerequisites

- [x] 0.1 Worktree `../Mapsurvey-layer-style` on `feature/layer-style` from `origin/master` (01b0e7d, #156 merged); `.env.ports` offset 20; `env` symlink; `.env`; `collectstatic` (2026-09-05)
- [ ] 0.2 Archive `overlay-features` and `respondent-shared-map` in the main checkout before this change archives (their deltas are the base text of the deltas here)

## 1. Model and normalisation (spec `layer-style`)

- [x] 1.1 `SurveyMapLayer.style` JSONField (default dict); migration `0073_layer_style`, reversible, no data
- [x] 1.2 `layers.normalize_style(raw) -> dict`: defaults, clamps, colour regex, icon allow-list (`LAYER_ICONS`, curated Font Awesome 5 solid names), ≤12 classes, rule dropped without a field, graduated classes sorted and contiguous; raises `LayerValidationError` only for >12 classes
- [x] 1.3 `layers.style_summary(layer, field)`: categorical values + counts (≤12 else too_many) / numeric min-max-count-quantiles
- [x] 1.4 `layers.legend_for(layer)`: rows per class, `other` only when unmatched objects exist (count them once per rebuild and cache on the layer? — no: compute in `build_map_layers_metadata`, it is metadata)
- [x] 1.5 Tests: defaults, clamps, colour fallback, icon allow-list, class cap, graduated ordering, summary on categorical / numeric / mixed, legend with and without `other`

## 2. Rendering (specs `layer-style`, `reference-overlay-layers` delta)

- [x] 2.1 `build_map_layers_metadata`: `style` (normalised) and `legend`
- [x] 2.2 Factory: `styleFor(meta, props, geomType)` — rule class → simplestyle → base; replace `featureStyle`, the `pointToLayer` colours and the tally offset; `divIcon` markers for icons (disc + glyph, 2·radius, coarse-pointer radius kept, fallback to circles above 1 000 icon points)
- [x] 2.3 CSS: `.ref-layer-icon`, legend rows (`.ref-layer-legend`, line / dot / icon samples)
- [x] 2.4 `reference_layers.html`: overlay label = name + legend HTML (escaped labels); expand the control once when a visible layer has a legend; `applyRefLayerVisibility` re-adds the same label
- [x] 2.5 Responses map (`analytics_geo_map.html`): legend rows in their layer panels from `meta.legend`; swatch shows base colour + "by attribute" pill
- [ ] 2.6 Object editor map (`layer_editor.html`) draws with its own code (drag/edit handles), not the factory — left as is; noted as follow-up in design. Public results has no reference layers, so 'public results map' in the proposal is moot
- [x] 2.7 Tests: metadata carries style/legend; rendered markup for the legend container and escaping; the four existing rendering tests still pass with an empty style

## 3. Editor (spec `survey-editor` delta, design D4)

- [ ] 3.1 `editor_survey_layer_update`: accept `style` (JSON string), normalise, 400 with the reason on `LayerValidationError`; payload returns the normalised style
- [ ] 3.2 `GET …/layers/<id>/style-summary/?field=` endpoint (owner, 404 under kill switch / for `question` layers)
- [ ] 3.3 Card template: Style block per mockup (base controls; switch; property picker from `_layer_property_names`; mode tabs; class table; other row; auto-fill; legend switch); `question` layers: base only
- [ ] 3.4 Card JS (`survey_settings_panel.html`): state → `style` JSON on change (debounced), auto-fill via the summary endpoint with the Okabe-Ito palette / viridis-like ramp and quantile or equal breaks, live preview mini-map re-styled from a ≤300-object subset, unmatched-count warning, "by attribute" pill on the head row
- [ ] 3.5 Tests: update endpoint (valid, clamped, too many classes → 400, question layer base-only); summary endpoint; card markup (block present, question layer without rule editor); browser pass on dev for the JS

## 4. Serialization (spec `survey-serialization` delta)

- [ ] 4.1 `serialize_layers` writes `style`; `_clean_layer_config` normalises it; legacy archives default
- [ ] 4.2 Tests: round-trip; edited archive clamped

## 5. Verification and close-out

- [ ] 5.1 Full suite once after; `openspec validate --strict layer-style`
- [ ] 5.2 Browser pass on the dev stand with the Sarasota export (worktree `responses-reference-layers` dev has it; or a synthetic 4-class segments layer): rule by `priority_class`, graduated by `priority_score`, icons on a points layer, legend on respondent / Responses / public results, mobile tap targets unchanged. Screenshots into the change folder
- [ ] 5.3 CLAUDE.md: a paragraph on `style` normalisation being the one validator and the factory being the one styling site
- [ ] 5.4 PR to master; Discord `#announcements` after merge; ping mrgmiami (Sarasota) with the preview — they are the design partner for this
