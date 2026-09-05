## Why

A reference layer has one colour. Sarasota/Manatee MPO (creator `mrgmiami`) loaded 6 119 road
segments that already carry `priority_score` / `priority_class` and had to split them into
four layers — one per class — to show priority at all, hitting the layer cap on the way. Every
municipal dataset arrives with an attribute that *is* the story (status, class, score, year), and
today the only way to show it is to pre-bake simplestyle colours into the file or fragment the
data into layers. Creators also cannot set opacity, line width, point size or an icon at all.

## What Changes

- **A per-layer `style`**: base style (colour, opacity, line width, point size, point icon)
  replacing the single colour picker, plus **one optional rule by attribute** — *categories*
  (value → colour / width / icon / legend label) or *graduated* (numeric breaks → colour ramp
  and width range). Render priority: rule → simplestyle in the file → base. `SurveyMapLayer.color`
  stays as the base colour so nothing that reads it changes.
- **Style block on the Reference layers card** in Survey settings: base controls, the rule
  editor with "Auto-fill from data" (distinct values / quantile breaks from the objects, with
  counts), editable legend labels, an "other" class, live preview on the card.
- **Legend for respondents** inside the layers control: one block per layer that has a rule
  (colour/width sample + label), toggle-able per layer by the creator. The same style and legend
  render on the Responses map and the public results map through the one shared factory.
- **Point icons**: a Font Awesome glyph per layer, and per class under a categories rule.
- **ZIP round-trip** of the `style` field through the whitelist cleaner.
- Not in scope: several rules per layer, per-object style overrides in the object editor
  (simplestyle in the file already covers it), clustering, image icons, "size by votes" on
  respondents' layers (recorded as v2 in design).

## Capabilities

### New Capabilities
- `layer-style`: the style model (base + one rule), its validation and defaults, the rendering
  contract shared by respondent, Responses and public maps, and the legend.

### Modified Capabilities
- `reference-overlay-layers`: *Respondent map renders reference layers beneath answers* gains the
  style precedence and the legend.
- `survey-editor`: *Reference layers card in Survey settings* replaces the colour picker with the
  Style block.
- `survey-serialization`: *Reference layers serialization* carries `style`.

Prerequisite: `overlay-features` and `respondent-shared-map` are merged but not archived; the
deltas here restate their latest text. Archive them first, then this change.

## Impact

- `survey/models.py`: `SurveyMapLayer.style` JSONField (default `{}`); one migration, no data.
- `survey/layers.py`: `normalize_style()` (whitelist + defaults + validation), `style_summary()`
  (distinct values / numeric range / counts for the editor), `legend_for()`.
- `survey/templates/partials/ref_layer_factory.html`: one `styleFor(meta, props)` replacing the
  three styling sites; icons via `L.divIcon`; legend HTML for the layers control.
- `survey/templates/partials/reference_layers.html`, `analytics_geo_map.html`, public results
  map: legend rendering; metadata (`build_map_layers_metadata`) carries `style` and `legend`.
- `survey/editor_views.py` + `survey_settings_panel.html`: Style block, `style` on the update
  endpoint, a `style-summary` endpoint for auto-fill.
- `survey/serialization.py`: `style` in the layer config + cleaner.
- Tests: normalisation, summary, metadata/legend, endpoint validation, card markup, ZIP.
- No new kill switch; `MAP_REFERENCE_LAYERS` gates all of it.
