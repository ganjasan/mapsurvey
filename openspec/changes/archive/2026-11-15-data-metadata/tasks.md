## 1. Model and rule

- [x] 1.1 `Dataset.theme`, `maintainer`, `update_frequency`; `licence` closed list; migration
- [x] 1.2 `data/fields.py`: closed lists, `hidden_names(layer_id)`, `public_properties`, `dictionary(dataset)`, `card_fields`, `merge_private`

## 2. Enforcement

- [x] 2.1 `layers._object_props`/`stream_layer_geojson`/`feature_for_object`: drop hidden names, `property_names` without them
- [x] 2.2 metadata: private `label_field` → none, rule on a private field dropped; `style_summary` empty for a private field
- [x] 2.3 REST/MCP `object_out`; `services.layers.update_object` keeps private values
- [x] 2.4 ZIP export objects; budget cost property

## 3. Dataset page

- [x] 3.1 view + route `/editor/data/<id>/`, access rule, details form, dictionary save (rebuild when private set changes)
- [x] 3.2 download (GeoJSON, CSV) with labels, no private fields
- [x] 3.3 catalogue rows link to the page
- [x] 3.4 respondent card lists public documented fields

## 4. Ship

- [x] 4.1 tests `survey/tests/test_data_metadata.py` (+ UNMAPPED_MODULES entry)
- [x] 4.2 translations, help page, CLAUDE.md
- [x] 4.3 full suite, /verify with screenshot, PR into epic/data
