## Why

Platform rule: every module's create, edit and publish is in the API and MCP on the day it ships
(#674, Data epic #676). An agent must be able to upload a register, describe it and show it in a
survey with the Data module's own tools.

## What Changes

- **`data.services`**: the one write path of the Data module, taking an `Actor` — details, access,
  fields, tags, views, uploads, versions, deletes, survey links. The dataset page now calls it too.
- **REST API v1** (`api/v1/datasets.py`, scopes `surveys:read` / `surveys:write`):
  - `GET /datasets`, `GET /datasets/{id}`, `GET /datasets/{id}/features` (layers, private fields left out;
    collected answers → 409, read a grid view instead), `PATCH /datasets/{id}`, `PUT /datasets/{id}/fields`,
    `DELETE /datasets/{id}`;
  - `POST /datasets` (upload job), `POST /datasets/{id}/versions`, `GET /dataset-jobs/{id}`,
    `POST /dataset-jobs/{id}/apply`;
  - `POST /datasets/{id}/views`, `GET /datasets/{id}/views/{view}/features`, `DELETE …/views/{view}`;
  - `POST /surveys/{uuid}/datasets`, `DELETE /surveys/{uuid}/datasets/{link}`.
- **MCP tools** over the same schemas and helpers: `list_datasets`, `get_dataset`, `upload_dataset`
  (file as text or base64), `get_dataset_job`, `update_dataset`, `set_dataset_fields`,
  `create_dataset_view`, `upload_dataset_version`, `apply_dataset_version`, `link_dataset`,
  `unlink_dataset`.
- Generated `reference/api.md` and `reference/mcp-tools.md` regenerated.

## Capabilities

### New Capabilities
- `data-api`: the Data module in REST API v1 and MCP.

### Modified Capabilities
<!-- none -->

## Impact

- `data/services.py` (new), `data/views.py` (calls it), `api/v1/datasets.py` (new), `api/v1/__init__.py`,
  `mcp/tools/data.py` (new), `mcp/tools/__init__.py`; help reference pages; CLAUDE.md.
