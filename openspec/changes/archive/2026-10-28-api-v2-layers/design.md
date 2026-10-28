## Context

Layer and object writes live in views: `editor_views.editor_survey_layer_create|update|delete`
(owner) and `layer_object_views` (owner; `_layer_write` lock; read-only on `source='question'`
layers). Request-free helpers already exist in `survey/layers.py`: `validate_layer_upload`,
`objects_from_features`, `explode_geometry`, `derive_key`, `rebuild_layer`, `check_object_caps`,
`normalize_style`, `layer_owner`/`layers_for` (canonical ownership, geometry deferred). Shared-map
layers are created by `services.questions._resolve_layer_choice` on `layer='answers:<code>'`, which
REST cannot reach (`layer_id` int). No layer write is audited; no live-survey lock applies to layers
(the object editor shows a banner instead). `LayerObject.link` is never validated.

## Goals / Non-Goals

**Goals:** an agent can create a layer from GeoJSON, style it, edit its objects, bind a question to it
(existing `layer_id`) or turn a geo question's answers into a shared map, and moderate marks; the
editor and the API run the same code; the link hole is closed.

**Non-Goals:** object attachments (photos, audio, embeds); CSV and photo-batch imports; content CSV;
per-section `hidden_layers` (a question setting); reprojection.

## Decisions

### D1 · A layer service, views become thin
`survey/services/layers.py` takes an `Actor` and plain values: `create_from_geojson(actor, survey,
name, data_bytes|features)`, `create_empty`, `update(actor, layer, fields)`, `delete`, `reorder`,
`create_object`, `update_object`, `delete_object`, `set_object_status`. It owns the caps
(`MAX_LAYERS_PER_SURVEY`, `check_object_caps`), the lock (`_layer_write` moves here), `rebuild_layer`
after every write, `normalize_style`, the label/key-field rule, the PROTECT refusal and the audit
row. Refusals are `services.errors.ValidationFailed` (`fields`) / a new `LayerInUse`; the editor
views map them to the JSON they return today (status and message unchanged), the API to its envelope.

### D2 · Upload transport
REST accepts `application/json` `{name?, geojson: <object>}` on `POST …/layers` (the agent's natural
form) and `multipart/form-data` `file` + `name` on `POST …/layers/upload` -- two routes, because one
ninja operation cannot document both bodies; both become the bytes `validate_layer_upload` reads, so caps
and messages are the editor's. Name defaults to the file stem / "New layer". MCP takes `geojson` as
an object (same 10 MB cap on the serialised size).

### D3 · Roles and live surveys
Layer and object writes: survey role `owner` (parity with the editor). Mark moderation: `editor`.
Scope `surveys:write` for every write. A published survey's layers stay editable (the editor allows
it); responses carry `live: true` so the agent can say respondents see the change now.

### D4 · Shared maps through the question routes
`layer_from_answers: <code>` on `POST`/`PATCH` question (exclusive with `layer_id`) becomes
`data['layer'] = 'answers:<code>'` in `forms_bridge`, so `_resolve_layer_choice` runs unchanged
(including its structure lock). It now also respects `MAX_LAYERS_PER_SURVEY` when it would create a
layer (it did not). Objects of a `question` layer are read-only over the API, as in the editor;
`PATCH …/objects/{key}/status` sets `visible|pending|hidden` (`analytics_object_status` logic).

### D5 · Links: one rule, enforced twice
`layers.clean_object_link(value)` → `''` or an `http(s)://` URL ≤500 chars, else
`LayerValidationError`. The API and the editor's PATCH refuse a bad link (400 naming `link`);
imports (GeoJSON mapping, CSV, ZIP manifest) drop it silently into the report (`invalid_links: n`)
rather than fail a whole file. The respondent card (`object_card_payload` and the JS that renders
it) shows `href` only for http(s), so links stored before the fix are inert.

### D6 · Output shapes
Layer = REST v1 `out.layer` plus `color, label_field, key_field, show_popups, style, legend,
source_question_code, live`. Object = `{key, title, category, description, link, geometry,
properties, position, answers}` (no assets). Lists of objects are cursor-paginated (default 100).

### D7 · Audit choices
`AuditLog.ACTION_CHOICES` gains the actions blocks 1–3 write; migration `0103` alters choices only.

## Risks / Trade-offs

- [Moving view logic into a service can change editor behaviour] → the editor's existing layer tests
  stay green; error statuses and messages are asserted unchanged.
- [An agent edits a live layer by mistake] → `live: true`, audit rows, owner role.
- [A big inline GeoJSON in an MCP call] → 10 MB cap before parsing; the MCP request size limit
  applies first.
