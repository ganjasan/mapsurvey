## Why

Uploaded files arrive with field names like `TR_HGT_M`, no licence and no owner, and sometimes a
personal column (an inspector's email) that must never reach a public map (#669, Data epic #676).
The upload (#668) already records a field dictionary with a private flag, but nothing reads it yet:
the flag is a promise no surface keeps.

## What Changes

- **Dataset page** `/editor/data/<id>/`, opened from the catalogue row: details (name, description,
  theme, maintainer, update frequency, licence from a closed list — OGL v3, CC BY 4.0, CC0,
  dl-de/by-2-0), the source and its facts, and for a layer the **field dictionary** (label, type,
  description, private) and a download.
- New `Dataset` columns: `theme` (the DCAT-AP data themes), `maintainer`, `update_frequency`;
  `licence` gets its closed list. Fields carry a `description`.
- **A private field never leaves the dataset's own editor.** One rule, `data.fields`, applied
  where object properties are turned into output: the derived layer GeoJSON (so the respondent map,
  the Responses map, the gated layer endpoint, the REST/MCP layer GeoJSON), REST/MCP object reads,
  the survey ZIP export, the editor's property pickers (label field, style by, key mapping,
  Auto-fill summary), a layer's label field and style rule in map metadata, a budget's cost
  property, and the dataset download. A write through the API cannot erase a private value it
  could not see.
- **Labels replace raw names**: the respondent object card lists the dictionary's public fields
  as "label: value"; the dataset download uses labels as column names / property keys.
- Tags stay with #673; Site blocks reach datasets in #670 and will use the same card payload.

## Capabilities

### New Capabilities
- `data-metadata`: the dataset page — details, field dictionary, private fields kept out of every
  output, labels in place of raw names, the dataset download.

### Modified Capabilities
<!-- none: data-upload's detector already proposes private fields; this change enforces them -->

## Impact

- Code: `data/models.py` (+ migration), `data/fields.py` (new), `data/views.py`, templates
  `data/dataset.html`; `survey/layers.py`, `survey/layer_assets.py`, `survey/serialization.py`,
  `survey/services/layers.py`, `survey/budget.py`, `api/v1/layers.py`, the respondent card in
  `partials/layer_objects_block.html`.
- Saving a dictionary whose private set changed rebuilds the layer's derived GeoJSON.
- Help page `how-to/data.md`, CLAUDE.md, strings in 10 catalogs.
