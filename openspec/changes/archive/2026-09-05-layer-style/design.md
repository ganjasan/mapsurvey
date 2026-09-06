# Design: layer-style

## Context

`SurveyMapLayer` carries one `color`. `ref_layer_factory.html` is the single place reference
layers are drawn — respondent shell, Responses map, public results and the object editor all
call `RefLayerFactory.build(meta, fc, opts)` — and it already lets simplestyle properties in
the file (`stroke`, `stroke-width`, `fill`, `fill-opacity`, `marker-color`) win over the layer
colour. Points are `L.circleMarker` (radius 6, 11 on coarse pointers). The layers control is
`L.control.layers` with the layer name as the overlay label. The object editor exposes an
object's raw `properties`; `_layer_property_names()` lists them for the label/key pickers.

Case: Sarasota/Manatee MPO, 6 119 segments with `priority_class` (4 values) and
`priority_score` (3–97), split into four layers. Mockup: `layer-style-editor.mockup.html`.

## Goals / Non-Goals

**Goals**
- One layer can look like four: colour/width/size/icon driven by one object property.
- Base look controllable without touching the file: opacity, width, point size, icon.
- Respondents can read the map: a legend where a rule exists.
- One styling function for every map surface; no drift between respondent and Responses.

**Non-Goals**
- Several rules per layer, expressions, per-object overrides in the editor, clustering,
  image icons, label styling. "Size by tally" on `question` layers is v2.

## Decisions

### D1. One JSON field, one shape

```python
SurveyMapLayer.style = JSONField(default=dict)
# normalised shape (normalize_style fills every key):
{
  "opacity": 0.9, "weight": 2, "fill_opacity": 0.15, "radius": 6, "icon": "",
  "by": None | {
    "field": "priority_class",
    "mode": "categories" | "graduated",
    "classes": [ {"value": "High", "color": "#d62828", "weight": 5, "radius": 9, "icon": "", "label": "High priority"}, ... ],
    # graduated: classes carry "from"/"to" instead of "value"; "ramp" and "weight_range" are the
    # editor's generators, stored so re-opening the card shows what was chosen
    "ramp": ["#8ecae6", "#d62828"], "weight_range": [2, 6], "breaks": "quantiles",
    "other": {"color": "#bbbbbb", "weight": 1, "radius": 5, "opacity": 0.4, "label": "Other"}
  },
  "legend": True
}
```

`color` stays a model column — the base colour — because the settings card, ZIP, the
Responses swatches and `_layer_payload` all read it; `style` never duplicates it.
`normalize_style()` is the one validator: unknown keys dropped, numbers clamped
(opacity 0–1, weight 0–12, radius 2–20), colours `#RRGGBB`, icon from the allow-list,
at most 12 classes, a rule whose `field` is empty is dropped. It runs on the update endpoint
and on import, the same posture as `_clean_layer_config`.

### D2. Rendering: `styleFor(meta, props, geomType)` in the factory

Precedence, per feature: **rule class** (matched by value or range on `props[field]`,
else `other`) → **simplestyle** in `props` → **base** (`style` + `color`). The three
existing sites (`featureStyle`, `pointToLayer`, the tally badge offset) collapse into one
function returning `{color, weight, opacity, fillColor, fillOpacity, radius, icon}`.
Points with an icon become `L.marker` with an `L.divIcon` (Font Awesome glyph on a
coloured disc, size = 2·radius, class `ref-layer-icon`), which keeps the tap-target rule
(radius 11 on coarse pointers) and the tooltip anchoring. Points without an icon stay
`circleMarker`. Matching for categories compares `String(value)`; graduated uses
`from <= v < to` with the last class inclusive.

### D3. Legend lives in the layers control

`build_map_layers_metadata` adds `style` (normalised) and `legend` (a list of
`{label, color, weight, radius, icon, kind}` rows computed server-side by `legend_for()`,
so the three maps never compute it differently). `reference_layers.html` passes an HTML
overlay label to `L.control.layers`: the name plus, when `style.legend` and a rule exist,
a `<div class="ref-layer-legend">` with one row per class (`other` last, only when it
has objects). The control is collapsed by default; a survey with a rule expands it once on
first load so the legend is seen. Responses and public results render the same rows in
their own layer panels from the same `legend` array.

### D4. The card: base controls + rule editor, auto-fill from the data

The settings card's colour picker becomes a *Style* block (mockup section 1): base
controls, a "Style by attribute" switch, property picker (from `_layer_property_names`),
mode tabs, the class table. **Auto-fill** calls `GET .../layers/<id>/style-summary/?field=X`
which returns distinct values with counts (up to 12, else "too many values, use graduated
or pick another field") or `{min, max, count}` for numeric fields, and the client builds
classes with a default palette (categories: a 12-colour qualitative set; graduated:
`quantiles` or `equal` breaks over a ramp). Every generated value is editable; the table
is what gets saved. Saving posts `style` as JSON to the existing update endpoint. The card
shows a live preview by re-styling a small `L.geoJSON` of up to 300 objects of the layer.
`question` layers get the base block only (their objects carry no properties).

### D5. Serialization

`style` joins the layer config in the ZIP; `_clean_layer_config` runs `normalize_style`.
Older archives without `style` import with the default. Export of a layer whose objects
carry simplestyle keeps them — the two coexist by D2.

### D6. Caps and performance

A rule adds one property lookup per feature at build time; 5 000 features is the existing
cap and Leaflet already styles per feature. Icons as `divIcon` are DOM nodes, heavier than
SVG paths: the factory falls back to circle markers above 1 000 visible points with an icon
and the card says so. The legend is metadata, not geometry, so the gated endpoint and its
caching are untouched.

## Risks / Trade-offs

- **Property values drift** after a re-import (renamed class, new values): unmatched
  features fall into `other`, visibly grey and dashed, and the card shows a warning with
  the count of unmatched objects. Silent black paint would hide the problem.
- **Colour-blind palettes**: the default qualitative set is Okabe-Ito (8 colours) extended
  to 12; graduated ramps are viridis-like by default. Creators can still pick red/green.
- **Legend and `hidden_layers`**: a layer hidden on a section takes its legend with it,
  because the legend is part of the overlay label.
- **`color` and `style.by` disagree** in the swatch on the card: the swatch shows the base
  colour; a rule-styled layer shows a small "by attribute" pill next to it.

## Migration Plan

One migration adding `style` (default `{}`), reversible. No data migration: an empty
`style` normalises to today's look (opacity 0.9, weight 2, fill 0.15, radius 6, no rule).

## Open Questions

- Icon set: Font Awesome 5 solid is loaded everywhere; a curated list of ~40 glyphs
  (bins, bus, tree, warning, school, parking…) or the full set with a search box? Curated
  first — the picker is on a settings card, not a design tool.
- Should `question` layers get "size by votes" in this change as a third mode? Kept out;
  it needs tallies in the metadata path and a different legend. v2.
