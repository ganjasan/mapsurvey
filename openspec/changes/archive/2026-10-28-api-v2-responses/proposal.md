## Why

An agent connected through MCP builds and publishes surveys but cannot read what came back. On
2026-10-24 Claude, asked for a report, replied that the connection has no tool to read responses —
while the consent page had just granted `responses:read` ("Read and export responses"). REST v1 has
the raw list and a file export, but no aggregates, no per-question geometry, no way to hand a person
a download in a chat, and no moderation. Block 1 of epic #408 (#409): REST first (PR 1), then the
MCP tools over it (PR 2).

## What Changes

**REST (PR 1)**
- `GET /surveys/{uuid}/responses/summary` — overall counts and, per question in section order,
  the Responses Overview's statistics: choice distributions (with the most frequent "other"
  write-ins), number/range/rating stats, text and geo counts, `layer_objects` aggregates; the
  sub-questions of geo and Objects questions nested under their parent.
- `GET /surveys/{uuid}/questions/{id}/answers` — text answers of one question, paginated.
- `GET /surveys/{uuid}/questions/{id}/geojson` — one geo question's answers as a FeatureCollection,
  sub-question values as properties (the export's collector).
- `POST /surveys/{uuid}/export-link` — a signed URL valid 15 minutes; `GET` on it builds the same
  file `download_data` builds, after checking rights and Pro again.
- `PATCH /surveys/{uuid}/responses/{id}` — `validation_status` (`approved`, `not_approved`,
  `on_hold`, `""`); audited; shared-map layers rebuilt.
- One session scope for summary, GeoJSON, answers and export: the export's — no empty sessions, no
  deleted, no `not_approved` unless `include_all`; `completed_only` and `version` as in export.
- New scope `responses:moderate`: on the token form and the consent page a switch, off by default,
  with its own note (it can be undone, unlike publish/delete).
- The editor's status change writes the same audit row (it wrote none).

**MCP (PR 2)**
- Tools `get_response_summary`, `list_responses`, `list_text_answers`, `get_answer_geojson`,
  `get_export_link`, `moderate_response` over the routes above; respondent text inside `data`.
- The help page's "It does not read responses in this version" is replaced; the tool reference is
  regenerated.

## Capabilities

### New Capabilities

### Modified Capabilities
- `rest-api-v1`: summary, text answers, per-question GeoJSON, export link, moderation; one session
  scope.
- `api-access-rights`: the scopes registry gains `responses:moderate`.
- `oauth-authorization-server`: the consent page shows `responses:moderate` as an off-by-default
  switch with its own note.
- `mcp-server`: response tools.

## Impact

`api/v1/` (routes, schemas, a new `responses.py`), `api/scopes.py`, `api/oauth/` consent and token
form, `survey/analytics.py` (question stats over a session subset, write-in counts, sub-question
stats), `survey/export.py` (one geo layer), `survey/analytics_views.py` (audit), `mcp/tools/`,
generated `help/.../reference/api.md` and `mcp-tools.md`, `use-the-mcp-server.md`, catalogs. No
migration.
