## Why

REST v1 can only read reference layers and MCP cannot touch them, so an agent cannot add context to
a map or build an "Objects on the map" question — it binds to a layer that must already exist.
Block 3 of epic #408 (#411): REST first (PR 1), MCP on top (PR 2).

Mapping the code also turned up a stored-XSS hole: `LayerObject.link` is never validated server-side
(editor PATCH, CSV, GeoJSON and ZIP imports) and the respondent's object card puts it into `href`
after HTML escaping only — a `javascript:` link runs on a respondent's click. Today only a survey
owner can write it; an API in an agent's hands makes it reachable by prompt injection.

## What Changes

**REST (PR 1)**
- `POST /surveys/{uuid}/layers` — a layer from GeoJSON (JSON body `{name, geojson}` or a multipart
  `file`), through the editor's validator (10 MB, 5 000 features, WGS84, Z dropped, multi-part split)
  and object import; or an empty layer.
- `PATCH /surveys/{uuid}/layers/{id}` — name, color, label/key field, popups, `style` (through
  `normalize_style`); `DELETE` (refused while a question uses it); `PUT /surveys/{uuid}/layers/order`.
- Objects: `GET/POST /surveys/{uuid}/layers/{id}/objects`, `GET/PATCH/DELETE …/objects/{key}` —
  key, title, category, description (`coerce_creator_html`), link (http/https only), geometry (one
  part), properties; caps and `rebuild_layer` as in the object editor; read-only on shared-map layers.
- Shared map: `layer_from_answers: <geo question code>` on question create/update (the editor's
  `answers:` path); `PATCH …/objects/{key}/status` moderates a mark (visible / pending / hidden).
- Owner role for layer and object writes (as in the editor), editor for moderation; every write
  audited; answers on a live survey say `live: true`.
- Layer writes move out of the views into `survey/services/layers.py`; the editor views call it.

**Security fix (PR 1)**
- One `clean_object_link()` (http/https only, else refused or dropped on import) on every write path,
  and the respondent card renders `href` only for http(s) — existing bad links stop working too.

**Housekeeping (PR 1)**
- `AuditLog.ACTION_CHOICES` lists the actions blocks 1–3 write (`response_status`,
  `tracked_link_create|delete`, `embed_hosts_set`, `layer_*`, `layer_object_*`); state-only migration.

**MCP (PR 2)**
- `list_layers`, `create_layer`, `update_layer`, `delete_layer`, `reorder_layers`, `list_layer_objects`,
  `create|update|delete_layer_object`, `moderate_layer_object`.

## Capabilities

### New Capabilities

### Modified Capabilities
- `rest-api-v1`: layers stop being read-only.
- `mcp-server`: layer tools.
- `reference-overlay-layers`: object links are http(s) only, on every write path and on the card.

## Impact

New `survey/services/layers.py`, `api/v1/layers.py`; `survey/editor_views.py` and
`survey/layer_object_views.py` call the service; `survey/layers.py` (`clean_object_link`), CSV/ZIP
importers, `partials/layer_objects_block.html`; `api/v1/forms_bridge.py` / question schemas
(`layer_from_answers`); `survey/models.py` + migration `0103` (choices only); MCP tools; references.
