## Why

Issue #617 (epic #348, Sites v1.1 wave B; platform rule 7, ADR-001 move 5 first slice). The builder views wrote `Site*` rows themselves. The next changes — the Translations tab, templates, the API/MCP tools, the AI wizard — need the same writes with the same rules, without a request.

## What Changes

- `survey/services/sites.py` is the one writer: create, settings, duplicate, publish/unpublish, delete, review link, survey link/unlink, block save (add/edit, documents, map upload, results target, survey card), block duplicate/move/delete/reorder, event registration removal. An `Actor` and plain values in (block fields as a QueryDict-like), `ValidationFailed` / `BlockRefused` / `SitesFeatureRequired` out; audit rows for the lifecycle steps.
- `site_views.py` keeps access checks, the Pro gate on edits and the responses; it writes nothing itself. A test fails if a view writes a row again.
- No behaviour change for creators.

## Capabilities

### Modified Capabilities
- `survey-sites`: site writes go through one service.

## Impact

New `survey/services/sites.py`; `site_views.py` thinner; CLAUDE.md gains a Sites paragraph. No migration, no template change.
