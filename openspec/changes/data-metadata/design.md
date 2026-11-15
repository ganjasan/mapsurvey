## Context

`Dataset.fields` (from #668) is `[{name, label, type, private}]`. Object properties live in
`LayerObject.properties`; every consumer either reads the derived `SurveyMapLayer.geojson` (built
by `layers._object_props` through `stream_layer_geojson`) or reads `properties` directly (REST/MCP
`object_out`, the ZIP export, the object editor's detail, style summaries, budget costs).

## Decisions

1. **Enforce at the builder, not at each page.** `layers._object_props` takes the layer's hidden
   names and drops them; `stream_layer_geojson` leaves them out of `property_names` too. The cache
   is rebuilt when a dictionary's private set changes, so every reader of the cache (respondent
   map, Responses, gated endpoint, REST/MCP GeoJSON, Sites) follows without a code change, and the
   editor pickers that read `property_names` cannot offer a private field. Direct readers of
   `properties` call `data.fields.public_properties(props, hidden)`. Rejected: filtering in each
   view — the issue's "not only from one page" is exactly that failure mode.
2. **The dataset's own editor** is the dataset page and the object editor's detail panel
   (`layer_object_views._object_detail`) — both behind the editor role on the owning workspace.
   They show private values.
3. **A write cannot erase what it could not see.** `services.layers.update_object` merges the
   existing private values under a `properties` replacement; the object editor sends them anyway,
   REST/MCP clients never saw them.
4. **Dictionary for survey layers.** A layer dataset's dictionary is the stored `fields` merged with
   `layer.property_names` (new names get label = name, type text). Because a private name is always
   in `fields`, the union is complete although `property_names` omits private names.
5. **Labels.** The respondent card gets `fields: [{label, value}]` — public dictionary fields with a
   non-empty value, in dictionary order, values as plain text (escaped by the card). Empty
   dictionary (every survey layer until someone documents it) = nothing new on the card. Map styles
   and label fields keep matching raw names (they are keys, not text). The dataset download writes
   labels as keys.
6. **Closed lists.** Licence: `ogl-uk-3.0`, `cc-by-4.0`, `cc0-1.0`, `dl-de-by-2.0` (owner list
   2026-11-14). Theme: the 13 DCAT-AP data themes (EU vocabulary, what #675's open-data feed will
   publish). Update frequency: as needed, daily, weekly, monthly, quarterly, yearly, never.
7. **Who edits.** Owner/admin/editor of the workspace may edit a workspace upload; for a survey's
   dataset an editor must also be a collaborator of the survey (the catalogue's visibility rule).
   Viewers read.

## Risks

- A rebuild of a 100,000-object upload when its private set changes runs in the request (seconds).
  Accepted for v1: it happens on a deliberate save, and only when privacy changed.
- Existing style rules on a field that becomes private: the rule is dropped from the map metadata
  (no class labels leak in the legend); the stored style keeps it so un-privating restores it.
