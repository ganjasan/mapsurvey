## ADDED Requirements

### Requirement: Layer tools
The MCP server SHALL offer `list_layers` and `list_layer_objects` under `surveys:read`, and
`create_layer` (GeoJSON as an object argument), `update_layer`, `reorder_layers`, `delete_layer`,
`create_layer_object`, `update_layer_object`, `delete_layer_object` and `moderate_layer_object` under
`surveys:write`, each over the layer service the REST routes call, with the same roles and limits.
`delete_layer` and `delete_layer_object` SHALL require `confirm: true`.

#### Scenario: Map context from a chat
- **WHEN** an agent calls `create_layer` with a FeatureCollection of bus stops
- **THEN** the survey has a new layer with those stops as objects, and the result names its id for `layer_id` on a question

#### Scenario: Delete needs confirmation
- **WHEN** an agent calls `delete_layer` without `confirm`
- **THEN** the result is `confirmation_required` and the layer still exists
