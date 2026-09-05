## ADDED Requirements

### Requirement: A layer has a base style and at most one rule by attribute
`SurveyMapLayer` SHALL carry `style`: a base style (`opacity`, `weight`, `fill_opacity`,
`radius`, `icon`) and an optional rule `by` naming one object property with `mode`
`categories` (each class: `value`, `color`, `weight`, `radius`, `icon`, `label`) or `graduated`
(each class: `from`, `to`, `color`, `weight`, `radius`, `label`, ordered ascending), plus an
`other` class and a `legend` flag. The base colour SHALL remain `SurveyMapLayer.color`.
`normalize_style` SHALL be the only validator: unknown keys dropped, numbers clamped
(opacity 0–1, weight 0–12, radius 2–20), colours `#RRGGBB`, icons from the allow-list, at most
12 classes, and a rule without a field dropped. An empty `style` SHALL normalise to today's
look (opacity 0.9, weight 2, fill 0.15, radius 6, no icon, no rule, legend on).

#### Scenario: Empty style is today's look
- **WHEN** a layer saved before this change is normalised
- **THEN** `style` yields weight 2, opacity 0.9, fill 0.15, radius 6, no rule

#### Scenario: Invalid input is repaired, not rejected
- **WHEN** `style` arrives with `weight: 40`, `color: "red"` on a class and an unknown key
- **THEN** the weight is clamped to 12, the class colour falls back to the base colour, the key is dropped, and the layer saves

#### Scenario: Thirteen classes
- **WHEN** a categories rule with 13 classes is posted
- **THEN** the endpoint refuses with a message naming the limit

### Requirement: Every map surface styles features through one function
The reference-layer factory SHALL compute each feature's style as: the matching rule class
(categories by `String(value)` equality, graduated by `from <= value < to`, last class
inclusive; unmatched → `other`) → simplestyle properties in the feature → base style with
the layer colour. Points with an icon SHALL render as a glyph on a coloured disc of
diameter `2·radius` and keep the coarse-pointer tap-target rule; points without an icon
SHALL stay circle markers. The respondent map, the Responses map, the public results map
and the object editor SHALL all render through this function.

#### Scenario: Sarasota in one layer
- **WHEN** a segments layer has a categories rule on `priority_class` with four classes
- **THEN** each segment renders in its class colour and width on the respondent map, the Responses map and the public results map alike

#### Scenario: Unmatched value goes to other
- **WHEN** a feature's `priority_class` is `"Unknown"` and no class has that value
- **THEN** it renders with the `other` style

#### Scenario: File colours still win where no rule applies
- **WHEN** a layer has no rule and its features carry `stroke` / `stroke-width`
- **THEN** those render as before; base opacity and radius apply where the file is silent

#### Scenario: Icon markers
- **WHEN** a points layer sets icon `fa-trash` and radius 8
- **THEN** each point is a 16 px disc in the layer colour with the glyph, and 22 px on a coarse pointer

### Requirement: Respondents get a legend where a rule exists
`build_map_layers_metadata` SHALL carry the normalised `style` and a server-computed
`legend` (rows of label, colour, weight, radius, icon, kind) for layers with a rule and
`legend` on; the `other` row SHALL appear only when at least one object falls into it.
The respondent layers control SHALL show the legend rows under the layer's name, the
Responses and public results layer panels SHALL show the same rows, and a layer hidden on
a section SHALL take its legend with it. The control SHALL open once on first load when
any visible layer has a legend.

#### Scenario: Legend rows
- **WHEN** the segments layer has four classes and no unmatched objects
- **THEN** the control lists the layer name and four rows with a line sample of the class colour and width, and no "Other" row

#### Scenario: Legend off
- **WHEN** the creator switches "Show legend to respondents" off
- **THEN** the control shows only the layer name

### Requirement: Style summary for auto-fill
`GET /editor/surveys/<uuid>/layers/<id>/style-summary/?field=<name>` SHALL return, for a
property of the layer's objects, either `{"kind": "categories", "values": [{value, count}]}`
(at most 12 values, else `{"kind": "too_many", "count": n}`) or, when every non-empty value
is numeric, `{"kind": "numeric", "min", "max", "count", "quantiles": [...]}`. Owner only;
404 under the kill switch and for `question` layers.

#### Scenario: Categorical field
- **WHEN** the owner asks for `priority_class` on the segments layer
- **THEN** four values with their counts come back

#### Scenario: Numeric field
- **WHEN** the owner asks for `priority_score`
- **THEN** min 3, max 97, count 6 119 and the quartile breaks come back
