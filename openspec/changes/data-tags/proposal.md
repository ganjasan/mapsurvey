## Why

A council or a consultancy runs an engagement as a survey, a Site, a few datasets and (later) a report,
and has no way to see them together — and the platform deliberately has no "project" entity
(#673, Data epic #676; Platform Vision §2.4: tags group items into projects).

## What Changes

- **Free workspace tags** ("Riverside plan 2027"): typed on a dataset's page and on a survey's
  settings panel, created on first use, gone when nothing carries them.
- **A tag filter** on the Data catalogue and on the survey dashboard (`?tag=`); tags show on the rows
  and cards, and the dashboard search finds them.
- **API and MCP**: every survey carries `tags`; `GET /api/v1/surveys?tag=` and MCP `list_surveys(tag)`
  filter; `PUT /api/v1/surveys/{uuid}/tags` and MCP `set_survey_tags` replace a survey's tags
  (editor role). Datasets reach the API in #674 with their tags.
- Sites, map apps and reports take tags when they need them (same table, one more relation).

## Capabilities

### New Capabilities
- `data-tags`: workspace tags on datasets and surveys, filters, API and MCP.

### Modified Capabilities
<!-- none -->

## Impact

- `data/models.py` (`Tag` with `datasets` / `surveys` relations, migration), `data/tags.py` (new),
  `data/views.py`, Data templates; `survey/views.py` dashboard + `editor.html`; the survey settings
  panel and an editor endpoint; `api/v1/surveys.py`, `api/v1/out.py`, `api/v1/schemas.py`,
  `mcp/tools/surveys.py`; regenerated `reference/api.md` and `reference/mcp-tools.md`.
- Help pages, CLAUDE.md, strings in 10 catalogs.
